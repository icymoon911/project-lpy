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
# Declarative settings schema
# ---------------------------------------------------------------------------
# Each entry describes one persisted setting:
#   group      – QSettings group name
#   key        – QSettings key inside the group
#   type       – Python type used for conversion on read ('bool','int','float','str','list')
#   default    – default value (or callable returning one) when the key is missing
#   getter     – callable(lpywidget) -> value to persist
#   setter     – callable(lpywidget, value) -> None  to apply the read value
#
# Entries are processed in order by the generic _read_settings / _write_settings
# helpers so that adding a new preference only requires appending one row here.
# ---------------------------------------------------------------------------

def _get_codeeditor(w):
    return w.codeeditor

# -- simple attribute helpers ------------------------------------------------

def _attr_get(attr):
    """Return a getter that reads *attr* from the widget."""
    return lambda w: getattr(w, attr)

def _attr_set(attr):
    """Return a setter that writes *attr* on the widget."""
    return lambda w, v: setattr(w, attr, v)

# -- code-editor attribute helpers -------------------------------------------

def _ce_attr_get(attr):
    return lambda w: getattr(w.codeeditor, attr)

def _ce_attr_set(attr):
    return lambda w, v: setattr(w.codeeditor, attr, v)

def _ce_method_get(method):
    return lambda w: getattr(w.codeeditor, method)()

def _ce_method_set(method):
    return lambda w, v: getattr(w.codeeditor, method)(v)


# The schema list – every persisted setting in one place.
SETTINGS_SCHEMA = [
    # ---- history ----------------------------------------------------------
    dict(group='history', key='RecentFiles', type='list', default=[],
         getter=lambda w: list(w.history),
         setter=lambda w, v: setattr(w, 'history', [str(i) for i in v if i is not None and len(i) > 0])),
    dict(group='history', key='OpenedFiles', type='list', default=[],
         getter=lambda w: [str(i.getStrFname()) for i in w.simulations if i.fname is not None],
         setter=lambda w, v: setattr(w, '_openedfiles', [str(i) for i in v if i is not None and len(i) > 0])),
    dict(group='history', key='MaxSize', type='int', default=lambda w: w.historymaxsize,
         getter=lambda w: w.historymaxsize,
         setter=lambda w, v: setattr(w, 'historymaxsize', v)),
    dict(group='history', key='LastFocus', type='int', default=-1,
         getter=lambda w: w.currentSimulationId,
         setter=lambda w, v: setattr(w, '_lastfocus', v)),

    # ---- file -------------------------------------------------------------
    dict(group='file', key='reloadstartup', type='bool', default=True,
         getter=_attr_get('reloadAtStartup'),
         setter=_attr_set('reloadAtStartup')),
    dict(group='file', key='fileMonitoring', type='bool', default=True,
         getter=_attr_get('fileMonitoring'),
         setter=_attr_set('fileMonitoring')),
    dict(group='file', key='fileBackup', type='bool', default=True,
         getter=_attr_get('fileBackupEnabled'),
         setter=_attr_set('fileBackupEnabled')),
    dict(group='file', key='codeBackup', type='bool', default=True,
         getter=_attr_get('codeBackupEnabled'),
         setter=_attr_set('codeBackupEnabled')),

    # ---- compilation ------------------------------------------------------
    dict(group='compilation', key='showPythonCode', type='bool', default=False,
         getter=_attr_get('showPyCode'),
         setter=_attr_set('showPyCode')),
    dict(group='compilation', key='CCompilerPath', type='str', default='',
         getter=_attr_get('cCompilerPath'),
         setter=lambda w, v: w.setCCompilerPath(v)),

    # ---- threading --------------------------------------------------------
    dict(group='threading', key='activated', type='bool', default=False,
         getter=_attr_get('with_thread'),
         setter=_attr_set('with_thread')),

    # ---- view3D -----------------------------------------------------------
    dict(group='view3D', key='fitAnimationView', type='bool', default=True,
         getter=_attr_get('fitAnimationView'),
         setter=_attr_set('fitAnimationView')),
    dict(group='view3D', key='fitRunView', type='bool', default=True,
         getter=_attr_get('fitRunView'),
         setter=_attr_set('fitRunView')),
    dict(group='view3D', key='integratedView', type='bool', default=False,
         getter=_attr_get('use_own_view3D'),
         setter=lambda w, v: w.setIntegratedView3D(v)),
    dict(group='view3D', key='displayMetaInfoAtRun', type='bool', default=False,
         getter=_attr_get('displayMetaInfo'),
         setter=_attr_set('displayMetaInfo')),

    # ---- profiling --------------------------------------------------------
    dict(group='profiling', key='mode', type='int', default=1,
         getter=_attr_get('profilingMode'),
         setter=_attr_set('profilingMode')),

    # ---- application ------------------------------------------------------
    dict(group='application', key='svnLastRevisionChecked', type='int', default=0,
         getter=_attr_get('svnLastRevisionChecked'),
         setter=_attr_set('svnLastRevisionChecked')),
    dict(group='application', key='svnLastDateChecked', type='float', default=0.0,
         getter=_attr_get('svnLastDateChecked'),
         setter=_attr_set('svnLastDateChecked')),
    dict(group='application', key='safeLaunch', type='bool', default=False,
         getter=lambda w: getattr(w, 'safeLaunch', False),
         setter=_attr_set('safeLaunch')),

    # ---- syntax -----------------------------------------------------------
    dict(group='syntax', key='highlighted', type='bool', default=True,
         getter=lambda w: w.codeeditor.isSyntaxHighLightActivated(),
         setter=lambda w, v: (w.codeeditor.setSyntaxHighLightActivation(v),
                              w.actionSyntax.setChecked(v))),
    dict(group='syntax', key='tabview', type='bool', default=True,
         getter=lambda w: w.codeeditor.isTabHighLightActivated(),
         setter=lambda w, v: (w.codeeditor.setTabHighLightActivation(v),
                              w.actionTabHightlight.setChecked(v))),

    # ---- edition ----------------------------------------------------------
    dict(group='edition', key='replaceTab', type='bool', default=True,
         getter=_ce_attr_get('replaceTab'),
         setter=_ce_attr_set('replaceTab')),
    dict(group='edition', key='tabSize', type='int', default=2,
         getter=_ce_method_get('tabSize'),
         setter=_ce_method_set('setTabSize')),
]


# ---------------------------------------------------------------------------
# Type conversion helpers
# ---------------------------------------------------------------------------

def _convert(value, type_name, default):
    """Convert a QSettings value to the requested Python type."""
    if value is None:
        return default
    try:
        if type_name == 'bool':
            if isinstance(value, bool):
                return value
            return str(value).lower() == 'true'
        elif type_name == 'int':
            return int(value)
        elif type_name == 'float':
            return float(value)
        elif type_name == 'list':
            return list(value) if value is not None else []
        else:  # str
            return str(value)
    except (ValueError, TypeError):
        return default


def _resolve_default(default, widget):
    """Resolve a default that may be a callable taking the widget."""
    if callable(default):
        return default(widget)
    return default


# ---------------------------------------------------------------------------
# Generic read / write over the schema
# ---------------------------------------------------------------------------

def _read_settings(settings, schema, widget):
    """Read all *schema* entries from *settings* into *widget*."""
    for entry in schema:
        default = _resolve_default(entry['default'], widget)
        settings.beginGroup(entry['group'])
        try:
            raw = settings.value(entry['key'], to_qvariant(default))
            value = _convert(raw, entry['type'], default)
            entry['setter'](widget, value)
        except Exception:
            pass
        settings.endGroup()


def _write_settings(settings, schema, widget):
    """Write all *schema* entries from *widget* into *settings*."""
    for entry in schema:
        settings.beginGroup(entry['group'])
        try:
            value = entry['getter'](widget)
            settings.setValue(entry['key'], to_qvariant(value))
        except Exception:
            pass
        settings.endGroup()


# ---------------------------------------------------------------------------
# Appearance group – needs special handling (fonts, geometry, dock count …)
# ---------------------------------------------------------------------------

def _read_appearance(settings, widget):
    settings.beginGroup('appearance')
    try:
        nbDock = int(settings.value('nbMaxDocks'))
        widget.setObjectPanelNb(nbDock, True)
    except Exception:
        pass
    if not widget.safeLaunch and settings.contains('state'):
        ba = bytearray(settings.value('state'))
        if ba:
            widget.restoreState(ba, 0)
    if settings.contains('geometryState'):
        widget.restoreGeometry(settings.value('geometryState'))
    try:
        tbapp = str(settings.value('toolbarStyle', to_qvariant(widget.getToolBarApp()[1])))
        widget.setToolBarApp(tbapp)
    except Exception:
        pass
    if settings.contains('editionfont'):
        f = QFont()
        fstr = str(from_qvariant(settings.value('editionfont')))
        if fstr != 'default' and f.fromString(fstr):
            widget.codeeditor.setEditionFont(f)
    settings.endGroup()


def _write_appearance(settings, widget):
    settings.beginGroup('appearance')
    settings.setValue('nbMaxDocks', to_qvariant(widget.getMaxObjectPanelNb()))
    settings.setValue('state', to_qvariant(widget.saveState(0)))
    settings.setValue('geometryState', to_qvariant(widget.saveGeometry()))
    settings.setValue('toolbarStyle', to_qvariant(widget.getToolBarApp()[1]))
    if not widget.codeeditor.isFontToDefault():
        settings.setValue('editionfont', to_qvariant(widget.codeeditor.editionFont.toString()))
    else:
        settings.setValue('editionfont', 'default')
    settings.endGroup()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def restoreState(lpywidget):
    try:
        settings = getSettings()

        # Schema-driven read for the majority of settings
        _read_settings(settings, SETTINGS_SCHEMA, lpywidget)

        # Appearance needs special handling (geometry, fonts, docks)
        _read_appearance(settings, lpywidget)

        if settings.status() != QSettings.NoError:
            raise Exception('settings error')
        del settings

        # Post-read actions that depend on multiple values
        openedfiles = getattr(lpywidget, '_openedfiles', [])
        lastfocus = getattr(lpywidget, '_lastfocus', -1)

        # Safe-mode CLI overrides
        import sys
        if '--safe' in sys.argv:
            lpywidget.safeLaunch = True
        if '--no-safe' in sys.argv:
            lpywidget.safeLaunch = False

        if lpywidget.reloadAtStartup and len(openedfiles) > 0:
            for f in openedfiles:
                if os.path.exists(f):
                    lpywidget.openfile(f)
            if lastfocus != -1 and os.path.exists(openedfiles[lastfocus]):
                try:
                    lpywidget.openfile(openedfiles[lastfocus])
                except Exception:
                    pass
    except Exception as e:
        print("cannot restore correctly state from ini file:", e)


def saveState(lpywidget):
    print('Save state')
    settings = getSettings()

    # Schema-driven write for the majority of settings
    _write_settings(settings, SETTINGS_SCHEMA, lpywidget)

    # Appearance needs special handling
    _write_appearance(settings, lpywidget)

    if settings.status() != QSettings.NoError:
        raise Exception('settings error')
    settings.sync()
