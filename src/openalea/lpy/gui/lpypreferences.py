from openalea.plantgl.gui.qt import qt
from openalea.plantgl.gui.qt.QtCore import QObject, Signal
from openalea.plantgl.gui.qt.QtWidgets import QDialog, QFileDialog
import os

from .lpyprofiling import AnimatedProfiling, ProfilingWithFinalPlot, ProfilingWithNoPlot
from . import generate_ui
from . import lpyprefwidget


# ---------------------------------------------------------------------------
# Declarative binding table
# ---------------------------------------------------------------------------
#
# Each tuple describes how one widget in the preferences dialog binds to one
# property of the ``LPyWindow`` (the "editor") or of its ``codeeditor``.
#
#   (widget_attr, signal, target_obj, target_attr_or_method,
#    setter_name, getter_kind)
#
# * ``widget_attr``  : attribute name on ``self.widget`` (the Ui object).
# * ``signal``       : name of the Qt signal to connect (e.g. ``'clicked'``,
#                      ``'valueChanged'``).
# * ``target_obj``   : ``'editor'`` or ``'codeeditor'`` – which object the
#                      widget reads from / writes to.
# * ``target_attr``  : attribute or method name on the target object.
# * ``setter_name``  : optional method name on the target that accepts the
#                      signal value (used for codeeditor setters such as
#                      ``setTabSize``).  When ``None`` we fall back to
#                      ``setattr(target, target_attr, value)``.
# * ``getter_kind``  : ``'value'`` – call ``widget.value()`` to read initial;
#                      ``'checked'`` – call ``widget.isChecked()``;
#                      ``None`` – do not set an initial value (handled
#                      elsewhere).
# ---------------------------------------------------------------------------

PREF_BINDINGS = [
    # (widget_attr,    signal,          target_obj,   target_attr,         setter_name,        getter_kind)
    ('startupReloadEdit', 'clicked',    'editor',     'reloadAtStartup',   None,               'checked'),
    ('fileMonitoringEdit','clicked',    'editor',     'fileMonitoring',    None,               'checked'),
    ('fileBackupEdit',    'clicked',    'editor',     'fileBackupEnabled', None,               'checked'),
    ('codeBackupEdit',    'clicked',    'editor',     'codeBackupEnabled', None,               'checked'),
    ('historySizeEdit',   'valueChanged','editor',    'historymaxsize',    None,               'value'),
    ('pycodeDebugEdit',   'clicked',    'editor',     'showPyCode',        None,               'checked'),
    ('useThreadEdit',     'clicked',    'editor',     'with_thread',       None,               'checked'),
    ('fitViewAnimateEdit','clicked',    'editor',     'fitAnimationView',  None,               'checked'),
    ('fitViewRunEdit',    'clicked',    'editor',     'fitRunView',        None,               'checked'),
    ('visuInfoEdit',      'clicked',    'editor',     'displayMetaInfo',   None,               'checked'),
    ('spaceForTabEdit',   'clicked',    'codeeditor', 'replaceTab',        'setReplaceTab',    'checked'),
    ('tabSizeEdit',       'valueChanged','codeeditor','tabSize',           'setTabSize',       'value'),
    ('integratedViewEdit','clicked',    'editor',     'use_own_view3D',    'setIntegratedView3D','checked'),
]


class LpyPreferences:
    def __init__(self, lpyeditor):
        self.editor = lpyeditor
        self.widget = None
        self.dialog = None

    # ------------------------------------------------------------------ show
    def show(self):
        self.dialog = QDialog(self.editor)
        self.widget = lpyprefwidget.Ui_PreferenceDialog()
        self.widget.setupUi(self.dialog)

        self._bind_toolbar()
        self._bind_font()
        self._bind_compiler_path()
        self._bind_profiling()

        # Declarative bindings -------------------------------------------
        for (widget_attr, signal_name, target_key, attr_name,
             setter_name, getter_kind) in PREF_BINDINGS:
            widget = getattr(self.widget, widget_attr)
            target = self.editor if target_key == 'editor' else self.editor.codeeditor

            # Initialise widget from editor state
            if getter_kind == 'checked':
                widget.setChecked(getattr(target, attr_name))
            elif getter_kind == 'value':
                widget.setValue(getattr(target, attr_name)() if callable(getattr(target, attr_name, None)) else getattr(target, attr_name))

            # Connect signal → setter
            signal = getattr(widget, signal_name)
            if setter_name is not None:
                setter = getattr(target, setter_name)
                signal.connect(setter)
            else:
                # Use setattr; capture target/attr_name in defaults to avoid
                # the old lambda-closure-in-a-loop pitfall.
                signal.connect(
                    lambda value, _t=target, _a=attr_name: setattr(_t, _a, value)
                )

        self.widget.textOutputBox.setEnabled(False)
        self.dialog.show()

    # ------------------------------------------------------- toolbar / font
    def _bind_toolbar(self):
        self.widget.toolbarAppEdit.setCurrentIndex(self.editor.getToolBarApp()[0])
        self.widget.toolbarAppEdit.activated.connect(self.editor.setToolBarApp)

    def _bind_font(self):
        self.widget.fontFamilyEdit.setCurrentFont(self.editor.codeeditor.currentFont())
        self.widget.fontSizeEdit.setValue(self.editor.codeeditor.currentFont().pointSize())
        self.widget.fontFamilyEdit.currentFontChanged.connect(self.editor.codeeditor.setEditionFontFamily)
        self.widget.fontSizeEdit.valueChanged.connect(self.editor.codeeditor.setEditionFontSize)

    # ----------------------------------------------------- compiler path
    def _bind_compiler_path(self):
        self.widget.gccPathEdit.setText(self.editor.cCompilerPath)
        self.widget.gccPathButton.clicked.connect(self.chooseCCompilerPath)
        self.widget.gccPathEdit.returnPressed.connect(self.editor.setCCompilerPath)

    # --------------------------------------------------------- profiling
    def _bind_profiling(self):
        self.setProfilingButton(self.editor.profilingMode)
        self.widget.profilingAnimatedButton.clicked.connect(self.setProfilingAnimMode)
        self.widget.profilingFinalPlotButton.clicked.connect(self.setProfilingFinalPlotMode)
        self.widget.profilingNoPlotButton.clicked.connect(self.setProfilingNoPlotMode)

    # -------------------------------------------------- individual helpers
    def chooseCCompilerPath(self):
        p = QFileDialog.getExistingDirectory(self.editor, "Choose Compiler Path", self.editor.cCompilerPath)
        if len(p) > 0:
            self.widget.gccPathEdit.setText(p)
            self.editor.setCCompilerPath(p)

    def reSetCCompilerPath(self):
        self.editor.setCCompilerPath(self.widget.gccPathEdit.text())

    def setProfilingAnimMode(self, enabled):
        if enabled:
            self.editor.profilingMode = AnimatedProfiling

    def setProfilingFinalPlotMode(self, enabled):
        if enabled:
            self.editor.profilingMode = ProfilingWithFinalPlot

    def setProfilingNoPlotMode(self, enabled):
        if enabled:
            self.editor.profilingMode = ProfilingWithNoPlot

    def setProfilingButton(self, value):
        """Set the profiling radio button matching *value*."""
        if value == AnimatedProfiling:
            self.widget.profilingAnimatedButton.setChecked(True)
        elif value == ProfilingWithFinalPlot:
            self.widget.profilingFinalPlotButton.setChecked(True)
        else:
            self.widget.profilingNoPlotButton.setChecked(True)

    # Backwards-compatible alias – old typo "setPofilingButton" may be
    # referenced from external code; keep it working but delegate to the
    # correctly-spelled version.
    setPofilingButton = setProfilingButton
