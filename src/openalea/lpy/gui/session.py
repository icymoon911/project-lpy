"""
Session export / import for LPy simulations.

A ".lpysession" file is a JSON document that captures the full running
context of one simulation: L-system code, derivation length, scalar
parameters, visual-parameter panels (curves, functions, NURBS patches,
...), description fields and the list of external Python modules that
were monitored at export time.

The format is forward-compatible: unknown keys are ignored on import,
and objects whose manager type is not available in the current
environment are skipped with a warning instead of crashing.
"""

import json
import os
import sys
import traceback
import warnings

# ---------------------------------------------------------------------------
# Format version -- bump when the schema changes in an incompatible way.
# ---------------------------------------------------------------------------
SESSION_FORMAT_VERSION = "1.0"
SESSION_FILE_EXTENSION = ".lpysession"


# ---------------------------------------------------------------------------
# Helpers -- scalar serialization
# ---------------------------------------------------------------------------

def _scalar_to_json(scalar):
    """Serialize a *Scalar object (Bool/Integer/Float/Category/Enum)
    into a JSON-friendly dict.

    We reuse the ``totuple()`` representation that is already used by
    ``__reduce__`` and by the L-system initialisation code.  It is a
    plain tuple of built-in types, so it maps directly to JSON.
    """
    return list(scalar.totuple())


def _scalar_from_json(jdata):
    """Reverse of :func:`_scalar_to_json`."""
    from openalea.lpy.lsysparameters.scalar import ProduceScalar
    return ProduceScalar(jdata)


# ---------------------------------------------------------------------------
# Helpers -- panel-object serialization
# ---------------------------------------------------------------------------

def _object_to_json(manager, obj):
    """Serialize one panel object together with its manager typename.

    If the manager provides a ``to_json`` method we use it.  Otherwise
    we fall back to the PlantGL json representation (``jsonrep``).
    """
    typename = manager.typename
    name = manager.getName(obj)
    try:
        data = manager.to_json(obj)
    except NotImplementedError:
        # Fallback: use plantgl json representation directly.
        try:
            import openalea.plantgl.algo.jsonrep as jr
            data = jr.to_json_rep(obj)
        except Exception as exc:
            warnings.warn("Cannot serialize object %r of type %r: %s"
                          % (name, typename, exc))
            return None
    except Exception as exc:
        warnings.warn("Cannot serialize object %r of type %r: %s"
                      % (name, typename, exc))
        return None
    return {"typename": typename, "name": name, "data": data}


def _object_from_json(jobj, managers):
    """Deserialize one panel object.

    Returns ``(manager, obj)`` or ``None`` if the typename is unknown
    or the reconstruction fails.
    """
    typename = jobj.get("typename")
    name = jobj.get("name", "<unnamed>")
    data = jobj.get("data")
    if typename is None:
        warnings.warn("Object %r has no typename -- skipped." % name)
        return None
    manager = managers.get(typename)
    if manager is None:
        warnings.warn("No manager for typename %r (object %r) -- skipped."
                      % (typename, name))
        return None
    try:
        import openalea.plantgl.algo.jsonrep as jr
        obj = jr.from_json_rep(data)
    except Exception as exc:
        warnings.warn("Cannot deserialize object %r of type %r: %s"
                      % (name, typename, exc))
        return None
    # Restore the name that may have been lost by the generic deserializer.
    try:
        manager.setName(obj, name)
    except Exception:
        pass
    return (manager, obj)


# ---------------------------------------------------------------------------
# Public API -- export
# ---------------------------------------------------------------------------

def export_session(simulation, fname, lpywidget=None):
    """Export *simulation* (an ``AbstractSimulation`` / ``LpySimulation``)
    to the JSON file *fname*.

    If *simulation* is not the current one, the caller must have called
    ``simulation.saveState()`` beforehand so that ``simulation.code``,
    ``simulation.scalars``, ``simulation.visualparameters`` and
    ``simulation.desc_items`` are up-to-date.

    Parameters
    ----------
    simulation : AbstractSimulation
        The simulation to export.
    fname : str
        Destination path (should end with ``.lpysession``).
    lpywidget : LPyWindow, optional
        The main window.  Used to retrieve monitored Python modules.
    """
    # Make sure the in-memory state is fresh.
    # (The caller may already have done this, but calling twice is safe.)
    if simulation.isCurrent():
        simulation.saveState()

    # -- code + derivation length -------------------------------------------
    code = simulation.code or ""
    derivation_length = None
    try:
        derivation_length = simulation.lsystem.derivationLength
    except Exception:
        pass

    # -- scalars ------------------------------------------------------------
    scalars = []
    for s in (simulation.scalars or []):
        try:
            scalars.append(_scalar_to_json(s))
        except Exception as exc:
            warnings.warn("Cannot serialize scalar %r: %s" % (s, exc))

    # -- visual parameters (panels) -----------------------------------------
    panels = []
    for panelinfo, objects in (simulation.visualparameters or []):
        jobjects = []
        for manager, obj in objects:
            jobj = _object_to_json(manager, obj)
            if jobj is not None:
                jobjects.append(jobj)
        panels.append({"info": dict(panelinfo), "objects": jobjects})

    # -- description items --------------------------------------------------
    desc_items = {}
    for key, value in (simulation.desc_items or {}).items():
        desc_items[key] = str(value) if value is not None else ""

    # -- monitored Python modules -------------------------------------------
    pymodules = []
    try:
        monitored = simulation.modulemonitor.modules
    except Exception:
        monitored = set()
    reference_dir = None
    if simulation.fname:
        reference_dir = os.path.abspath(os.path.dirname(simulation.fname))
    for modname in sorted(monitored):
        mod = sys.modules.get(modname)
        if mod is None:
            continue
        modfile = getattr(mod, "__file__", None)
        if modfile is None:
            continue
        modfile = os.path.abspath(modfile)
        if reference_dir and modfile.startswith(reference_dir):
            pymodules.append(os.path.relpath(modfile, reference_dir))
        else:
            pymodules.append(modfile)

    # -- timestep / autorun -------------------------------------------------
    timestep = getattr(simulation, "timestep", 50)
    autorun = getattr(simulation, "autorun", False)

    # -- assemble document --------------------------------------------------
    doc = {
        "format_version": SESSION_FORMAT_VERSION,
        "source_filename": simulation.fname or None,
        "code": code,
        "derivation_length": derivation_length,
        "timestep": timestep,
        "autorun": autorun,
        "scalars": scalars,
        "panels": panels,
        "desc_items": desc_items,
        "pymodules": pymodules,
    }

    with open(fname, "w", encoding="utf-8") as fout:
        json.dump(doc, fout, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API -- import
# ---------------------------------------------------------------------------

def import_session(fname):
    """Read a ``.lpysession`` file and return a plain ``dict`` that the
    GUI layer can use to populate a new simulation tab.

    The returned dict has the same keys as the JSON document, with
    panel objects already deserialized into ``(manager, obj)`` pairs
    whenever the matching manager exists.  Objects whose manager is
    missing are dropped (a warning is emitted).

    Returns
    -------
    dict
        Keys: ``code``, ``derivation_length``, ``timestep``, ``autorun``,
        ``scalars`` (list of ``*Scalar`` objects), ``panels`` (list of
        ``(panelinfo, [(manager, obj), ...])`` tuples), ``desc_items``,
        ``pymodules`` (list of paths), ``source_filename``,
        ``format_version``, ``missing_modules`` (list of module paths
        that do not exist on disk).
    """
    with open(fname, "r", encoding="utf-8") as fin:
        doc = json.load(fin)

    from .objectmanagers import get_managers
    managers = get_managers()

    # -- scalars ------------------------------------------------------------
    scalars = []
    for js in doc.get("scalars", []):
        try:
            scalars.append(_scalar_from_json(js))
        except Exception as exc:
            warnings.warn("Cannot deserialize scalar %r: %s" % (js, exc))

    # -- panels -------------------------------------------------------------
    panels = []
    skipped_objects = []
    for jpanel in doc.get("panels", []):
        info = jpanel.get("info", {"name": "Panel"})
        objects = []
        for jobj in jpanel.get("objects", []):
            pair = _object_from_json(jobj, managers)
            if pair is not None:
                objects.append(pair)
            else:
                skipped_objects.append(jobj.get("name", "<unnamed>"))
        panels.append((info, objects))

    # -- pymodules existence check ------------------------------------------
    missing_modules = []
    reference_dir = os.path.dirname(os.path.abspath(fname))
    for modpath in doc.get("pymodules", []):
        abspath = modpath if os.path.isabs(modpath) else os.path.join(reference_dir, modpath)
        if not os.path.exists(abspath):
            missing_modules.append(modpath)

    return {
        "format_version": doc.get("format_version"),
        "source_filename": doc.get("source_filename"),
        "code": doc.get("code", ""),
        "derivation_length": doc.get("derivation_length"),
        "timestep": doc.get("timestep", 50),
        "autorun": doc.get("autorun", False),
        "scalars": scalars,
        "panels": panels,
        "desc_items": doc.get("desc_items", {}),
        "pymodules": doc.get("pymodules", []),
        "missing_modules": missing_modules,
        "skipped_objects": skipped_objects,
    }


# ---------------------------------------------------------------------------
# Merge helper (for the CLI tool)
# ---------------------------------------------------------------------------

def merge_sessions(input_fnames, output_fname):
    """Merge panel objects from several ``.lpysession`` files into one.

    * The L-system code is taken from the **first** input file.
    * Scalars are concatenated (duplicates are kept -- the user can
      clean them up in the GUI).
    * Panels are concatenated: each input file's panels are appended in
      order.
    * Description items are merged key-by-key; the first non-empty
      value wins.
    * Python module lists are union-merged.

    The result is written to *output_fname*.
    """
    if not input_fnames:
        raise ValueError("No input files provided.")

    merged_code = None
    merged_derivation_length = None
    merged_timestep = 50
    merged_autorun = False
    merged_scalars = []
    merged_panels = []
    merged_desc_items = {}
    merged_pymodules = set()
    merged_format_version = SESSION_FORMAT_VERSION

    for fname in input_fnames:
        with open(fname, "r", encoding="utf-8") as fin:
            doc = json.load(fin)

        if merged_code is None:
            merged_code = doc.get("code", "")
            merged_derivation_length = doc.get("derivation_length")
            merged_timestep = doc.get("timestep", 50)
            merged_autorun = doc.get("autorun", False)

        # scalars -- keep raw JSON, no need to deserialize
        for js in doc.get("scalars", []):
            merged_scalars.append(js)

        # panels -- keep raw JSON (objects remain as JSON dicts)
        for jpanel in doc.get("panels", []):
            merged_panels.append(jpanel)

        # desc items -- first non-empty wins
        for key, value in doc.get("desc_items", {}).items():
            if key not in merged_desc_items or not merged_desc_items[key]:
                merged_desc_items[key] = value

        # pymodules -- union
        for mp in doc.get("pymodules", []):
            merged_pymodules.add(mp)

    out = {
        "format_version": merged_format_version,
        "source_filename": None,
        "code": merged_code or "",
        "derivation_length": merged_derivation_length,
        "timestep": merged_timestep,
        "autorun": merged_autorun,
        "scalars": merged_scalars,
        "panels": merged_panels,
        "desc_items": merged_desc_items,
        "pymodules": sorted(merged_pymodules),
    }

    with open(output_fname, "w", encoding="utf-8") as fout:
        json.dump(out, fout, indent=2, ensure_ascii=False)
