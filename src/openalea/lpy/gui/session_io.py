"""
Session import/export for LPy simulations.

A ".lpysession" file is a JSON document capturing the full run context of one
simulation:
  - L-system code
  - derivation length
  - scalar parameters
  - object panels (curves, functions, NURBS patches, ...)
  - description items (authors, description, copyright, ...)
  - monitored external Python module relative paths
  - exported file name (for provenance)
"""

import json
import os
import sys
import traceback

SESSION_FORMAT_VERSION = "1.0"


def _get_module_file_paths(module_monitor):
    """Return a list of file paths for modules tracked by *module_monitor*."""
    paths = []
    for modname in module_monitor.modules:
        mod = module_monitor.sysmodules.get(modname)
        if mod is None:
            continue
        fpath = getattr(mod, '__file__', None)
        if fpath:
            paths.append(os.path.abspath(fpath))
    return paths


def _make_relative_paths(paths, reference_dir):
    """Try to make *paths* relative to *reference_dir*. Fall back to absolute."""
    if not reference_dir:
        return list(paths)
    result = []
    for p in paths:
        try:
            result.append(os.path.relpath(p, reference_dir))
        except ValueError:
            # On Windows relpath fails when drives differ
            result.append(p)
    return result


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def export_simulation_to_dict(simulation):
    """Serialise *simulation* (``AbstractSimulation`` subclass) to a ``dict``.

    The simulation's state is saved first so that the latest GUI values are
    captured.  Returns a JSON-serialisable ``dict``.
    """
    # Make sure the latest GUI state is captured
    if simulation.isCurrent():
        simulation.saveState()

    # Reference directory for relative paths
    reference_dir = None
    if simulation.fname:
        reference_dir = os.path.dirname(os.path.abspath(simulation.fname))

    # L-system code (pure L-system, no init section)
    code = simulation.code

    # Derivation length
    derivation_length = simulation.lsystem.derivationLength

    # Description items
    desc_items = dict(simulation.desc_items)

    # Scalars – serialise via todict() when available, fall back to totuple()
    scalars = []
    for sc in simulation.scalars:
        try:
            scalars.append(sc.todict())
        except Exception:
            scalars.append({'__tuple__': sc.totuple()})

    # Panels / visual parameters
    panels = []
    visualparameters = simulation.visualparameters
    for panel_info, objects in visualparameters:
        panel_dict = {'info': dict(panel_info), 'objects': []}
        for manager, obj in objects:
            try:
                obj_json = manager.to_json(obj)
                panel_dict['objects'].append({
                    'typename': manager.typename,
                    'name': manager.getName(obj),
                    'data': obj_json,
                })
            except Exception:
                traceback.print_exc()
                # Skip objects that fail to serialise
        panels.append(panel_dict)

    # Monitored external Python module files
    module_files = _get_module_file_paths(simulation.modulemonitor)
    module_relative = _make_relative_paths(module_files, reference_dir)

    # Materials – turtle colour list customisations
    materials = []
    try:
        from openalea.plantgl.all import PglTurtle, Material, PyStrPrinter
        import openalea.plantgl.algo.jsonrep as jrep
        default_list = PglTurtle().getColorList()
        current_list = simulation.lsystem.context().turtle.getColorList()
        default_mat = Material('default')
        for i in range(len(current_list)):
            cmat = current_list[i]
            if (i >= len(default_list)
                    or cmat.isTexture()
                    or (not cmat.isSimilar(default_list[i]))
                    or cmat.name != default_list[i].name):
                if cmat.isTexture() or not cmat.isSimilar(default_mat):
                    jmat = jrep.to_json_rep(cmat)
                    jmat['index'] = i
                    jmat['name'] = cmat.name
                    materials.append(jmat)
    except Exception:
        traceback.print_exc()

    return {
        'format': 'lpysession',
        'version': SESSION_FORMAT_VERSION,
        'code': code,
        'derivation_length': derivation_length,
        'desc_items': desc_items,
        'scalars': scalars,
        'panels': panels,
        'module_files': module_relative,
        'materials': materials,
        'source_file': os.path.basename(simulation.fname) if simulation.fname else None,
    }


def export_simulation_to_file(simulation, filepath):
    """Serialise *simulation* and write the result to *filepath*."""
    data = export_simulation_to_dict(simulation)
    with open(filepath, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------

def _rebuild_scalar(raw):
    """Rebuild a scalar object from its JSON representation."""
    from openalea.lpy.lsysparameters.scalar import (
        ProduceScalar, ScalarTypesDict,
        BoolScalar, IntegerScalar, FloatScalar, CategoryScalar,
        scalar_from_json_rep,
    )
    if '__tuple__' in raw:
        return ProduceScalar(raw['__tuple__'])
    # Try the json-rep path first
    try:
        return scalar_from_json_rep(raw)
    except Exception:
        pass
    # Manual reconstruction
    stype = raw.get('type', 'Integer')
    cls = ScalarTypesDict.get(stype, IntegerScalar)
    kw = {k: v for k, v in raw.items() if k != 'type'}
    return cls(**kw)


def import_simulation_from_dict(data, lpywidget):
    """Create a new simulation tab in *lpywidget* from a session *data* dict.

    The caller is responsible for calling ``restoreState()`` on the returned
    simulation and for making it current.
    """
    from .simulation import LpySimulation

    # Save state of the current simulation before creating a new one
    if lpywidget.currentSimulationId is not None:
        lpywidget.currentSimulation().saveState()

    sim = LpySimulation(lpywidget, len(lpywidget.simulations))
    lpywidget.simulations.append(sim)
    sim.registerTab()

    # --- code ---
    code = data.get('code', '')
    derivation_length = data.get('derivation_length', None)

    sim.code = code
    if sim.textdocument:
        lpywidget.textEditionWatch = False
        sim.textdocument.clear()
        sim.textdocument.setPlainText(code)
        lpywidget.textEditionWatch = True

    if derivation_length is not None:
        try:
            sim.lsystem.derivationLength = int(derivation_length)
        except Exception:
            pass

    # --- desc_items ---
    raw_desc = data.get('desc_items', {})
    for key in list(sim.desc_items.keys()):
        sim.desc_items[key] = raw_desc.get(key, '')

    # --- scalars ---
    raw_scalars = data.get('scalars', [])
    scalars = []
    for raw in raw_scalars:
        try:
            scalars.append(_rebuild_scalar(raw))
        except Exception:
            traceback.print_exc()
    sim.scalars = scalars

    # --- panels (visual parameters) ---
    from .objectmanagers import get_managers
    managers = get_managers()

    raw_panels = data.get('panels', [])
    visualparameters = []
    skipped = []

    try:
        import openalea.plantgl.algo.jsonrep as jrep
    except ImportError:
        jrep = None

    for raw_panel in raw_panels:
        panel_info = raw_panel.get('info', {'name': 'Panel'})
        objects = []
        for raw_obj in raw_panel.get('objects', []):
            typename = raw_obj.get('typename', '')
            obj_data = raw_obj.get('data', {})
            obj_name = raw_obj.get('name', '')
            manager = managers.get(typename)
            if manager is None:
                skipped.append(typename)
                continue
            if jrep is None:
                skipped.append(typename)
                continue
            try:
                # For curve/function disambiguation
                if typename == 'Function' and 'is_function' not in obj_data:
                    obj_data['is_function'] = True
                elif typename == 'Curve2D' and 'is_function' not in obj_data:
                    obj_data['is_function'] = False
                obj = jrep.from_json_rep(obj_data)
                obj.name = obj_name
                objects.append((manager, obj))
            except Exception:
                traceback.print_exc()
                skipped.append(typename)
        visualparameters.append((panel_info, objects))

    sim.visualparameters = visualparameters

    # --- materials ---
    raw_materials = data.get('materials', [])
    if raw_materials and jrep is not None:
        try:
            for jmat in raw_materials:
                idx = jmat.pop('index', None)
                jmat.pop('name', None)
                if idx is not None:
                    mat = jrep.from_json_rep(jmat)
                    sim.lsystem.context().turtle.setMaterial(idx, mat)
        except Exception:
            traceback.print_exc()

    # Warnings
    if skipped:
        from openalea.plantgl.gui.qt.QtWidgets import QMessageBox
        unique = sorted(set(skipped))
        QMessageBox.warning(
            lpywidget,
            "Import Session",
            "The following object type(s) could not be restored because "
            "their manager is not available in this environment:\n\n"
            + "\n".join(unique)
        )

    # Module files hint
    module_files = data.get('module_files', [])
    if module_files:
        reference_dir = os.getcwd()
        missing = []
        for relpath in module_files:
            abspath = relpath if os.path.isabs(relpath) else os.path.join(reference_dir, relpath)
            if not os.path.exists(abspath):
                missing.append(relpath)
        if missing:
            from openalea.plantgl.gui.qt.QtWidgets import QMessageBox
            QMessageBox.warning(
                lpywidget,
                "Import Session - Missing Modules",
                "The following external Python module file(s) recorded in "
                "the session were not found on this machine:\n\n"
                + "\n".join(missing)
                + "\n\nThe simulation may not behave identically."
            )

    return sim


def import_simulation_from_file(filepath, lpywidget):
    """Load a ``.lpysession`` file and create a new simulation tab."""
    with open(filepath, 'r', encoding='utf-8') as fh:
        data = json.load(fh)

    if data.get('format') != 'lpysession':
        raise ValueError("Not a valid .lpysession file (missing format marker)")

    return import_simulation_from_dict(data, lpywidget)


# ---------------------------------------------------------------------------
# Merge helper (used by the lpy-session-merge CLI tool)
# ---------------------------------------------------------------------------

def merge_sessions(input_files, output_file):
    """Merge panel objects from several ``.lpysession`` files into one.

    The first file provides the code, derivation length, description items and
    scalars.  All panels from every input file are appended in order.
    """
    if not input_files:
        raise ValueError("No input files")

    sessions = []
    for fpath in input_files:
        with open(fpath, 'r', encoding='utf-8') as fh:
            sessions.append(json.load(fh))

    merged = dict(sessions[0])
    all_panels = []
    all_module_files = []
    seen_modules = set()
    for sess in sessions:
        all_panels.extend(sess.get('panels', []))
        for mf in sess.get('module_files', []):
            if mf not in seen_modules:
                seen_modules.add(mf)
                all_module_files.append(mf)

    merged['panels'] = all_panels
    merged['module_files'] = all_module_files
    merged['source_file'] = None

    with open(output_file, 'w', encoding='utf-8') as fh:
        json.dump(merged, fh, indent=2, ensure_ascii=False)
