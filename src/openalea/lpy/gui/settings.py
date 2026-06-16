from openalea.plantgl.gui.qt.compat import *
from openalea.plantgl.gui.qt import qt
from openalea.plantgl.gui.qt.QtCore import QSettings
from openalea.plantgl.gui.qt.QtGui import QFont
from openalea.plantgl.gui.qt.QtWidgets import QApplication
from openalea.lpy import LPY_VERSION_MAJOR
import os


def getSettings():
    settings = QSettings(QSettings.IniFormat, QSettings.UserScope,'OpenAlea','LPy'+str(LPY_VERSION_MAJOR))
    return settings


# ---------------------------------------------------------------------------
# Type helpers – centralise the handful of conversions that were previously
# scattered across restoreState / saveState with mixed styles (int(),
# ``== 'true'``, ``to_qvariant()``, ``from_qvariant()`` …).
# ---------------------------------------------------------------------------

def _to_bool(raw, default):
    """Convert a QSettings value to bool.

    QSettings may return the strings ``'true'`` / ``'false'`` (lower-cased)
    or an actual Python bool depending on the backend.  Fall back to
    *default* on any conversion error.
    """
    if raw is None:
        return bool(default)
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.lower() == 'true'
    try:
        return bool(raw)
    except Exception:
        return bool(default)


def _to_int(raw, default):
    if raw is None:
        return int(default)
    try:
        return int(raw)
    except Exception:
        return int(default)


def _to_float(raw, default):
    if raw is None:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


def _to_str(raw, default):
    if raw is None:
        return str(default)
    return str(raw)


def _to_str_list(raw, default):
    """Convert a QVariant list to ``list[str]``, dropping empty entries."""
    if raw is None:
        return list(default) if default else []
    try:
        result = [str(i) for i in list(raw) if i is not None and len(str(i)) > 0]
        return result
    except Exception:
        return list(default) if default else []


_TYPE_CONVERTERS = {
    'bool': _to_bool,
    'int': _to_int,
    'float': _to_float,
    'str': _to_str,
    'str_list': _to_str_list,
}


# ---------------------------------------------------------------------------
# Declarative schema
# ---------------------------------------------------------------------------
#
# Each entry is a dict describing *one* QSettings key:
#   group   – QSettings group (``beginGroup`` argument)
#   key     – QSettings key inside the group
#   type    – one of 'bool', 'int', 'float', 'str', 'str_list'
#   default – default value (may be a callable receiving ``lpywidget``)
#   get     – callable(lpywidget) returning the current value to persist
#   set     – callable(lpywidget, value) applying the restored value
#
# Entries that need more elaborate logic (side effects, branching on
# safe-mode, …) use ``set`` / ``get`` callables that keep the schema
# declarative while still expressing the original behaviour.
# ---------------------------------------------------------------------------

def _set_syntax_highlight(widget, value):
    widget.codeeditor.setSyntaxHighLightActivation(value)
    widget.actionSyntax.setChecked(value)


def _get_syntax_highlight(widget):
    return widget.codeeditor.isSyntaxHighLightActivated()


def _set_tab_highlight(widget, value):
    widget.codeeditor.setTabHighLightActivation(value)
    widget.actionTabHightlight.setChecked(value)


def _get_tab_highlight(widget):
    return widget.codeeditor.isTabHighLightActivated()


def _set_integrated_view(widget, value):
    widget.setIntegratedView3D(value)


def _get_integrated_view(widget):
    return widget.use_own_view3D


def _set_compiler_path(widget, value):
    widget.setCCompilerPath(value)


def _get_compiler_path(widget):
    return widget.cCompilerPath


def _set_tab_size(widget, value):
    try:
        widget.codeeditor.setTabSize(value)
    except Exception:
        pass


def _get_tab_size(widget):
    return widget.codeeditor.tabSize()


def _set_replace_tab(widget, value):
    widget.codeeditor.replaceTab = value


def _get_replace_tab(widget):
    return widget.codeeditor.replaceTab


def _set_safe_launch(widget, value):
    import sys as _sys
    result = value
    if '--safe' in _sys.argv:
        result = True
    if '--no-safe' in _sys.argv:
        result = False
    widget.safeLaunch = result


def _get_safe_launch(widget):
    return getattr(widget, 'safeLaunch', False)


SETTINGS_SCHEMA = [
    # -- history -----------------------------------------------------------
    {'group': 'history', 'key': 'RecentFiles', 'type': 'str_list',
     'default': [],
     'get': lambda w: list(w.history),
     'set': lambda w, v: setattr(w, 'history', v)},
    {'group': 'history', 'key': 'OpenedFiles', 'type': 'str_list',
     'default': [],
     'get': lambda w: [str(i.getStrFname()) for i in w.simulations if i.fname is not None],
     'set': lambda w, v: setattr(w, '_openedfiles', v)},
    {'group': 'history', 'key': 'MaxSize', 'type': 'int',
     'default': lambda w: w.historymaxsize,
     'get': lambda w: w.historymaxsize,
     'set': lambda w, v: setattr(w, 'historymaxsize', v)},
    {'group': 'history', 'key': 'LastFocus', 'type': 'int',
     'default': -1,
     'get': lambda w: w.currentSimulationId,
     'set': lambda w, v: setattr(w, '_lastfocus', v)},

    # -- file --------------------------------------------------------------
    {'group': 'file', 'key': 'reloadstartup', 'type': 'bool',
     'default': lambda w: w.reloadAtStartup,
     'get': lambda w: w.reloadAtStartup,
     'set': lambda w, v: setattr(w, 'reloadAtStartup', v)},
    {'group': 'file', 'key': 'fileMonitoring', 'type': 'bool',
     'default': lambda w: w.fileMonitoring,
     'get': lambda w: w.fileMonitoring,
     'set': lambda w, v: setattr(w, 'fileMonitoring', v)},
    {'group': 'file', 'key': 'fileBackup', 'type': 'bool',
     'default': lambda w: w.fileBackupEnabled,
     'get': lambda w: w.fileBackupEnabled,
     'set': lambda w, v: setattr(w, 'fileBackupEnabled', v)},
    {'group': 'file', 'key': 'codeBackup', 'type': 'bool',
     'default': lambda w: w.codeBackupEnabled,
     'get': lambda w: w.codeBackupEnabled,
     'set': lambda w, v: setattr(w, 'codeBackupEnabled', v)},

    # -- compilation -------------------------------------------------------
    {'group': 'compilation', 'key': 'showPythonCode', 'type': 'bool',
     'default': lambda w: w.showPyCode,
     'get': lambda w: w.showPyCode,
     'set': lambda w, v: setattr(w, 'showPyCode', v)},
    {'group': 'compilation', 'key': 'CCompilerPath', 'type': 'str',
     'default': '',
     'get': _get_compiler_path,
     'set': _set_compiler_path},

    # -- threading ---------------------------------------------------------
    {'group': 'threading', 'key': 'activated', 'type': 'bool',
     'default': lambda w: w.with_thread,
     'get': lambda w: w.with_thread,
     'set': lambda w, v: setattr(w, 'with_thread', v)},

    # -- view3D ------------------------------------------------------------
    {'group': 'view3D', 'key': 'fitAnimationView', 'type': 'bool',
     'default': lambda w: w.fitAnimationView,
     'get': lambda w: w.fitAnimationView,
     'set': lambda w, v: setattr(w, 'fitAnimationView', v)},
    {'group': 'view3D', 'key': 'fitRunView', 'type': 'bool',
     'default': lambda w: w.fitRunView,
     'get': lambda w: w.fitRunView,
     'set': lambda w, v: setattr(w, 'fitRunView', v)},
    {'group': 'view3D', 'key': 'integratedView', 'type': 'bool',
     'default': lambda w: w.use_own_view3D,
     'get': _get_integrated_view,
     'set': _set_integrated_view},
    {'group': 'view3D', 'key': 'displayMetaInfoAtRun', 'type': 'bool',
     'default': lambda w: w.displayMetaInfo,
     'get': lambda w: w.displayMetaInfo,
     'set': lambda w, v: setattr(w, 'displayMetaInfo', v)},

    # -- profiling ---------------------------------------------------------
    {'group': 'profiling', 'key': 'mode', 'type': 'int',
     'default': lambda w: w.profilingMode,
     'get': lambda w: w.profilingMode,
     'set': lambda w, v: setattr(w, 'profilingMode', v)},

    # -- application -------------------------------------------------------
    {'group': 'application', 'key': 'svnLastRevisionChecked', 'type': 'int',
     'default': lambda w: w.svnLastRevisionChecked,
     'get': lambda w: w.svnLastRevisionChecked,
     'set': lambda w, v: setattr(w, 'svnLastRevisionChecked', v)},
    {'group': 'application', 'key': 'svnLastDateChecked', 'type': 'float',
     'default': lambda w: w.svnLastDateChecked,
     'get': lambda w: w.svnLastDateChecked,
     'set': lambda w, v: setattr(w, 'svnLastDateChecked', v)},
    {'group': 'application', 'key': 'safeLaunch', 'type': 'bool',
     'default': False,
     'get': _get_safe_launch,
     'set': _set_safe_launch},

    # -- syntax ------------------------------------------------------------
    {'group': 'syntax', 'key': 'highlighted', 'type': 'bool',
     'default': True,
     'get': _get_syntax_highlight,
     'set': _set_syntax_highlight},
    {'group': 'syntax', 'key': 'tabview', 'type': 'bool',
     'default': True,
     'get': _get_tab_highlight,
     'set': _set_tab_highlight},

    # -- edition -----------------------------------------------------------
    {'group': 'edition', 'key': 'replaceTab', 'type': 'bool',
     'default': lambda w: w.codeeditor.replaceTab,
     'get': _get_replace_tab,
     'set': _set_replace_tab},
    {'group': 'edition', 'key': 'tabSize', 'type': 'int',
     'default': lambda w: w.codeeditor.tabSize(),
     'get': _get_tab_size,
     'set': _set_tab_size},
]


# ---------------------------------------------------------------------------
# Appearance group – kept separate because it mixes QSettings bytearray
# state, geometry, font and toolbar logic that does not fit the simple
# schema pattern above.
# ---------------------------------------------------------------------------

def _restore_appearance(settings, lpywidget):
    settings.beginGroup('appearance')
    try:
        nbDock = int(settings.value('nbMaxDocks'))
        lpywidget.setObjectPanelNb(nbDock, True)
    except Exception:
        pass
    if not lpywidget.safeLaunch and settings.contains('state'):
        ba = bytearray(settings.value('state'))
        if ba:
            lpywidget.restoreState(ba, 0)
    if settings.contains('geometryState'):
        lpywidget.restoreGeometry(settings.value('geometryState'))
    tbapp = str(settings.value('toolbarStyle', to_qvariant(lpywidget.getToolBarApp()[1])))
    lpywidget.setToolBarApp(tbapp)
    if settings.contains('editionfont'):
        f = QFont()
        fstr = str(from_qvariant(settings.value('editionfont')))
        if fstr != 'default' and f.fromString(fstr):
            lpywidget.codeeditor.setEditionFont(f)
    settings.endGroup()


def _save_appearance(settings, lpywidget):
    settings.beginGroup('appearance')
    settings.setValue('nbMaxDocks', to_qvariant(lpywidget.getMaxObjectPanelNb()))
    settings.setValue('state', to_qvariant(lpywidget.saveState(0)))
    settings.setValue('geometryState', to_qvariant(lpywidget.saveGeometry()))
    settings.setValue('toolbarStyle', to_qvariant(lpywidget.getToolBarApp()[1]))
    if not lpywidget.codeeditor.isFontToDefault():
        settings.setValue('editionfont', to_qvariant(lpywidget.codeeditor.editionFont.toString()))
    else:
        settings.setValue('editionfont', 'default')
    settings.endGroup()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _resolve_default(default, lpywidget):
    """Return the concrete default value, evaluating callables if needed."""
    if callable(default):
        return default(lpywidget)
    return default


def restoreState(lpywidget):
    try:
        settings = getSettings()

        # Schema-driven restore ------------------------------------------
        for entry in SETTINGS_SCHEMA:
            group = entry['group']
            key = entry['key']
            converter = _TYPE_CONVERTERS[entry['type']]
            default = _resolve_default(entry['default'], lpywidget)
            settings.beginGroup(group)
            try:
                raw = settings.value(key)
                value = converter(raw, default)
                entry['set'](lpywidget, value)
            except Exception:
                # Leave the widget default untouched on any per-key error.
                pass
            settings.endGroup()

        # Appearance (complex group) --------------------------------------
        _restore_appearance(settings, lpywidget)

        if settings.status() != QSettings.NoError:
            raise Exception('settings error')
        del settings

        # Post-restore side effects (open files from history) -------------
        openedfiles = getattr(lpywidget, '_openedfiles', [])
        lastfocus = getattr(lpywidget, '_lastfocus', -1)
        if lpywidget.reloadAtStartup and len(openedfiles) > 0:
            for f in openedfiles:
                if os.path.exists(f):
                    lpywidget.openfile(f)
            if lastfocus != -1 and lastfocus < len(openedfiles) and os.path.exists(openedfiles[lastfocus]):
                try:
                    lpywidget.openfile(openedfiles[lastfocus])
                except Exception:
                    pass
    except Exception as e:
        print("cannot restore correctly state from ini file:", e)


def saveState(lpywidget):
    print('Save state')
    settings = getSettings()

    # Schema-driven save --------------------------------------------------
    for entry in SETTINGS_SCHEMA:
        group = entry['group']
        key = entry['key']
        settings.beginGroup(group)
        try:
            value = entry['get'](lpywidget)
            settings.setValue(key, to_qvariant(value))
        except Exception:
            pass
        settings.endGroup()

    # Appearance (complex group) -----------------------------------------
    _save_appearance(settings, lpywidget)

    if settings.status() != QSettings.NoError:
        raise Exception('settings error')
    settings.sync()
