from openalea.plantgl.gui.qt import qt
from openalea.plantgl.gui.qt.QtCore import QObject, Signal
from openalea.plantgl.gui.qt.QtWidgets import QDialog, QFileDialog
import os
from .lpyprofiling import AnimatedProfiling, ProfilingWithFinalPlot, ProfilingWithNoPlot

from . import generate_ui
from . import lpyprefwidget


# ---------------------------------------------------------------------------
# Declarative preference bindings
# ---------------------------------------------------------------------------
# Each entry maps:
#   widget_attr  – attribute name on the Ui_PreferenceDialog widget
#   editor_attr  – attribute name on the LPyWindow editor (or None for custom)
#   signal       – signal name on the widget to connect ('clicked', 'valueChanged', …)
#   set_method   – optional method name on the editor to call instead of setattr
#                  (used when the editor exposes a setter rather than a plain attribute)
#
# The 'init' callable reads the current value from the editor and applies it
# to the widget.  The 'connect' callable wires the widget signal to the editor.
# ---------------------------------------------------------------------------

_SIMPLE_CHECK_BINDINGS = [
    # (widget_attr, editor_attr)
    ('startupReloadEdit',  'reloadAtStartup'),
    ('fileMonitoringEdit', 'fileMonitoring'),
    ('fileBackupEdit',     'fileBackupEnabled'),
    ('codeBackupEdit',     'codeBackupEnabled'),
    ('pycodeDebugEdit',    'showPyCode'),
    ('useThreadEdit',      'with_thread'),
    ('fitViewAnimateEdit', 'fitAnimationView'),
    ('fitViewRunEdit',     'fitRunView'),
    ('visuInfoEdit',       'displayMetaInfo'),
]

_SIMPLE_VALUE_BINDINGS = [
    # (widget_attr, editor_attr, signal)
    ('historySizeEdit', 'historymaxsize', 'valueChanged'),
]


class LpyPreferences:
    def __init__(self, lpyeditor):
        self.editor = lpyeditor
        self.widget = None
        self.dialog = None

    # ------------------------------------------------------------------
    # show() – build the dialog and bind everything declaratively
    # ------------------------------------------------------------------
    def show(self):
        self.dialog = QDialog(self.editor)
        self.widget = lpyprefwidget.Ui_PreferenceDialog()
        self.widget.setupUi(self.dialog)

        self._bind_toolbar()
        self._bind_font()
        self._bind_code_editor_prefs()
        self._bind_checkbox_prefs()
        self._bind_value_prefs()
        self._bind_compiler_path()
        self._bind_profiling()
        self._bind_integrated_view()
        self._bind_disabled_controls()

        self.dialog.show()

    # -- toolbar --------------------------------------------------------
    def _bind_toolbar(self):
        self.widget.toolbarAppEdit.setCurrentIndex(self.editor.getToolBarApp()[0])
        self.widget.toolbarAppEdit.activated.connect(self.editor.setToolBarApp)

    # -- font -----------------------------------------------------------
    def _bind_font(self):
        ce = self.editor.codeeditor
        self.widget.fontFamilyEdit.setCurrentFont(ce.currentFont())
        self.widget.fontSizeEdit.setValue(ce.currentFont().pointSize())
        self.widget.fontFamilyEdit.currentFontChanged.connect(ce.setEditionFontFamily)
        self.widget.fontSizeEdit.valueChanged.connect(ce.setEditionFontSize)

    # -- code-editor prefs (replaceTab, tabSize) -------------------------
    def _bind_code_editor_prefs(self):
        ce = self.editor.codeeditor
        self.widget.spaceForTabEdit.setChecked(ce.replaceTab)
        self.widget.spaceForTabEdit.clicked.connect(ce.setReplaceTab)
        self.widget.tabSizeEdit.setValue(ce.tabSize())
        self.widget.tabSizeEdit.valueChanged.connect(ce.setTabSize)

    # -- simple checkbox → editor attribute ------------------------------
    def _bind_checkbox_prefs(self):
        for widget_attr, editor_attr in _SIMPLE_CHECK_BINDINGS:
            w = getattr(self.widget, widget_attr)
            w.setChecked(getattr(self.editor, editor_attr))
            w.clicked.connect(lambda x, attr=editor_attr: setattr(self.editor, attr, x))

    # -- value-changed → editor attribute --------------------------------
    def _bind_value_prefs(self):
        for widget_attr, editor_attr, signal_name in _SIMPLE_VALUE_BINDINGS:
            w = getattr(self.widget, widget_attr)
            w.setValue(getattr(self.editor, editor_attr))
            getattr(w, signal_name).connect(
                lambda x, attr=editor_attr: setattr(self.editor, attr, x))

    # -- C compiler path -------------------------------------------------
    def _bind_compiler_path(self):
        self.widget.gccPathButton.clicked.connect(self.chooseCCompilerPath)
        self.widget.gccPathEdit.setText(self.editor.cCompilerPath)
        self.widget.gccPathEdit.returnPressed.connect(self.editor.setCCompilerPath)

    # -- profiling radio buttons -----------------------------------------
    def _bind_profiling(self):
        self.setProfilingButton(self.editor.profilingMode)
        self.widget.profilingAnimatedButton.clicked.connect(self.setProfilingAnimMode)
        self.widget.profilingFinalPlotButton.clicked.connect(self.setProfilingFinalPlotMode)
        self.widget.profilingNoPlotButton.clicked.connect(self.setProfilingNoPlotMode)

    # -- integrated 3D view ----------------------------------------------
    def _bind_integrated_view(self):
        self.widget.integratedViewEdit.setChecked(self.editor.use_own_view3D)
        self.widget.integratedViewEdit.clicked.connect(self.editor.setIntegratedView3D)

    # -- controls that are currently disabled ----------------------------
    def _bind_disabled_controls(self):
        self.widget.textOutputBox.setEnabled(False)

    # ------------------------------------------------------------------
    # Slot helpers
    # ------------------------------------------------------------------
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
        if value == AnimatedProfiling:
            self.widget.profilingAnimatedButton.setChecked(True)
        elif value == ProfilingWithFinalPlot:
            self.widget.profilingFinalPlotButton.setChecked(True)
        else:
            self.widget.profilingNoPlotButton.setChecked(True)

    # Keep backward-compatible alias for the old (misspelled) name
    setPofilingButton = setProfilingButton
