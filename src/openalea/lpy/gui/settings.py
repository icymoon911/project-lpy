from openalea.plantgl.gui.qt.compat import *
from openalea.plantgl.gui.qt import qt
from openalea.plantgl.gui.qt.QtCore import QSettings
from openalea.plantgl.gui.qt.QtGui import QFont
from openalea.plantgl.gui.qt.QtWidgets import QApplication
from openalea.lpy import LPY_VERSION_MAJOR
import os


def _to_bool(value):
    """Convert a QSettings value to bool, handling None, bool, and
    case-insensitive string representations ('true'/'True'/'TRUE', etc.)."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == 'true'


def getSettings():
    settings = QSettings(QSettings.IniFormat, QSettings.UserScope,'OpenAlea','LPy'+str(LPY_VERSION_MAJOR))
    return settings

def restoreState(lpywidget):
  try:
    settings = getSettings()
    settings.beginGroup('history')

    recentFilesValue = settings.value('RecentFiles')
    lpywidget.history = [ str(i) for i in list(recentFilesValue) if not i is None and len(i) > 0] if recentFilesValue is not None else []
    try:
        openedFilesValue = settings.value('OpenedFiles')
        openedfiles = [ str(i) for i in list(openedFilesValue) if not i is None and len(i) > 0] if openedFilesValue is not None else []
    except:
        openedfiles = ''
    try:
        val = int(settings.value('MaxSize',to_qvariant(lpywidget.historymaxsize)))
        lpywidget.historymaxsize = val
    except:
        pass
    try :
        lastfocus = int(settings.value('LastFocus',to_qvariant(-1)))
    except:
        lastfocus = -1
    settings.endGroup()
    settings.beginGroup('file')
    # settings.value send "true" if value is "True" (and "false" if it is "False")
    lpywidget.reloadAtStartup = _to_bool(settings.value('reloadstartup',lpywidget.reloadAtStartup))
    lpywidget.fileMonitoring = _to_bool(settings.value('fileMonitoring',lpywidget.fileMonitoring))
    lpywidget.fileBackupEnabled = _to_bool(settings.value('fileBackup',lpywidget.fileBackupEnabled))
    lpywidget.codeBackupEnabled = _to_bool(settings.value('codeBackup',lpywidget.codeBackupEnabled))
    settings.endGroup()
    settings.beginGroup('compilation')
    lpywidget.showPyCode = _to_bool(settings.value('showPythonCode',lpywidget.showPyCode))
    lpywidget.setCCompilerPath(settings.value('CCompilerPath',str('')))
    settings.endGroup()
    settings.beginGroup('threading')
    lpywidget.with_thread = _to_bool(settings.value('activated',lpywidget.with_thread))
    settings.endGroup()
    settings.beginGroup('view3D')
    lpywidget.fitAnimationView = _to_bool(settings.value('fitAnimationView',lpywidget.fitAnimationView))
    lpywidget.fitRunView = _to_bool(settings.value('fitRunView',lpywidget.fitRunView))
    lpywidget.setIntegratedView3D(_to_bool(settings.value('integratedView',lpywidget.use_own_view3D)))
    lpywidget.displayMetaInfo = _to_bool(settings.value('displayMetaInfoAtRun',lpywidget.displayMetaInfo))
    settings.endGroup()
    settings.beginGroup('profiling')
    try:
        lpywidget.profilingMode = int(settings.value('mode',lpywidget.profilingMode))
    except:
        pass
    settings.endGroup()
    settings.beginGroup('application')
    lpywidget.svnLastRevisionChecked = int(settings.value('svnLastRevisionChecked',lpywidget.svnLastRevisionChecked))
    lpywidget.svnLastDateChecked = float(settings.value('svnLastDateChecked',lpywidget.svnLastDateChecked))
    lpywidget.safeLaunch = _to_bool(settings.value('safeLaunch',False))
    import sys
    if '--safe' in sys.argv:    lpywidget.safeLaunch = True
    if '--no-safe' in sys.argv:    lpywidget.safeLaunch = False
    settings.endGroup()
    settings.beginGroup('syntax')
    syntaxhlght = _to_bool(settings.value('highlighted',True))
    lpywidget.codeeditor.setSyntaxHighLightActivation(syntaxhlght)
    lpywidget.actionSyntax.setChecked(syntaxhlght)
    tabhlght = _to_bool(settings.value('tabview',True))
    lpywidget.codeeditor.setTabHighLightActivation(tabhlght)
    lpywidget.actionTabHightlight.setChecked(tabhlght)
    settings.endGroup()
    settings.beginGroup('appearance')
    try:
        nbDock  = int(settings.value('nbMaxDocks'))
        lpywidget.setObjectPanelNb(nbDock,True)
    except:
        pass  
    if not lpywidget.safeLaunch and settings.contains('state'):
        ba = bytearray(settings.value('state'))
        if ba : lpywidget.restoreState(ba,0);
    if settings.contains('geometryState'):
        lpywidget.restoreGeometry(settings.value('geometryState'))
    tbapp = str(settings.value('toolbarStyle',to_qvariant(lpywidget.getToolBarApp()[1])))
    lpywidget.setToolBarApp(tbapp)
    if settings.contains('editionfont'):
        f = QFont()
        fstr = str(from_qvariant(settings.value('editionfont')))
        if fstr != 'default' and f.fromString(fstr):
            #print 'read font',fstr
            lpywidget.codeeditor.setEditionFont(f)
    settings.endGroup()
    
    #settings.beginGroup('stdout')
    #lc = settings.value('lpyshell',True)=='true'
    #sc = settings.value('sysconsole',False)=='true'
    #lpywidget.shellwidget.setOutputRedirection(lc,sc,1)
    #settings.endGroup()
    
    #settings.beginGroup('stderr')
    #lc = settings.value('lpyshell',True)=='true'
    #sc = settings.value('sysconsole',False)=='true'
    #lpywidget.shellwidget.setOutputRedirection(lc,sc,2)
    #settings.endGroup()
    
    settings.beginGroup('edition')
    lpywidget.codeeditor.replaceTab = _to_bool(settings.value('replaceTab',lpywidget.codeeditor.replaceTab))
    try:
        val = int(settings.value('tabSize',lpywidget.codeeditor.tabSize()))
        lpywidget.codeeditor.setTabSize(val)
    except:
        pass
    settings.endGroup()

    if settings.status() != QSettings.NoError:
        raise Exception('settings error')
    del settings
    
    if lpywidget.reloadAtStartup and len(openedfiles) > 0:
        for f in openedfiles:
            if os.path.exists(f):
                lpywidget.openfile(f)
        if lastfocus != -1 and os.path.exists(openedfiles[lastfocus]):
            try:
                lpywidget.openfile(openedfiles[lastfocus])
            except:
                pass
  except Exception as e:
    print("cannot restore correctly state from ini file:", e)

def saveState(lpywidget):
    print('Save state')
    settings = getSettings()
    settings.beginGroup('history')
    settings.setValue('RecentFiles',to_qvariant(list(lpywidget.history)))
    op = list([str(i.getStrFname()) for i in lpywidget.simulations if not i.fname is None])
    settings.setValue('OpenedFiles',to_qvariant(op))
    settings.setValue('MaxSize',to_qvariant(lpywidget.historymaxsize))
    settings.setValue('LastFocus',to_qvariant(lpywidget.currentSimulationId))
    settings.endGroup()
    settings.beginGroup('file')
    settings.setValue('reloadstartup',to_qvariant(lpywidget.reloadAtStartup))
    settings.setValue('fileMonitoring',to_qvariant(lpywidget.fileMonitoring))
    settings.setValue('fileBackup',to_qvariant(lpywidget.fileBackupEnabled))
    settings.setValue('codeBackup',to_qvariant(lpywidget.codeBackupEnabled))
    settings.endGroup()
    settings.beginGroup('threading')
    settings.setValue('activated',to_qvariant(lpywidget.with_thread)) 
    settings.endGroup()
    settings.beginGroup('view3D')
    settings.setValue('fitAnimationView',to_qvariant(lpywidget.fitAnimationView)) 
    settings.setValue('fitRunView',to_qvariant(lpywidget.fitRunView)) 
    settings.setValue('integratedView',to_qvariant(lpywidget.use_own_view3D))
    settings.setValue('displayMetaInfoAtRun',to_qvariant(lpywidget.displayMetaInfo))
    settings.endGroup()
    settings.beginGroup('compilation')
    
    settings.setValue('showPythonCode',to_qvariant(lpywidget.showPyCode))
    
    settings.setValue('CCompilerPath',to_qvariant(lpywidget.cCompilerPath))
    settings.endGroup()
    settings.beginGroup('edition')
    settings.setValue('replaceTab',to_qvariant(lpywidget.codeeditor.replaceTab)) 
    settings.setValue('tabSize',to_qvariant(lpywidget.codeeditor.tabSize())) 
    settings.endGroup()
    settings.beginGroup('application')
    settings.setValue('svnLastRevisionChecked',to_qvariant(lpywidget.svnLastRevisionChecked))
    settings.setValue('svnLastDateChecked',to_qvariant(lpywidget.svnLastDateChecked))
    if hasattr(lpywidget,'safeLaunch') : settings.setValue('safeLaunch',to_qvariant(lpywidget.safeLaunch))
    settings.endGroup()
    settings.beginGroup('appearance')
    settings.setValue('nbMaxDocks',to_qvariant(lpywidget.getMaxObjectPanelNb()))    
    settings.setValue('state',to_qvariant(lpywidget.saveState(0))) 
    settings.setValue('geometryState',to_qvariant(lpywidget.saveGeometry())) 
    settings.setValue('toolbarStyle',to_qvariant(lpywidget.getToolBarApp()[1]))
    if not lpywidget.codeeditor.isFontToDefault():
        settings.setValue('editionfont',to_qvariant(lpywidget.codeeditor.editionFont.toString()))
    else:
        settings.setValue('editionfont','default')
    settings.endGroup()
    # if not lpywidget.interpreter is None:
    #     settings.beginGroup('stdout')
    #     outinshell = lpywidget.shellwidget.hasMultipleStdOutRedirection() or lpywidget.shellwidget.isSelfStdOutRedirection()
    #     outinsys   = lpywidget.shellwidget.hasMultipleStdOutRedirection() or lpywidget.shellwidget.isSysStdOutRedirection()
    #     settings.setValue('lpyshell',to_qvariant(outinshell))
    #     settings.setValue('sysconsole',to_qvariant(outinsys))
    #     settings.endGroup()
    #     settings.beginGroup('stderr')
    #     errinshell = lpywidget.shellwidget.hasMultipleStdErrRedirection() or lpywidget.shellwidget.isSelfStdErrRedirection()
    #     errinsys   = lpywidget.shellwidget.hasMultipleStdErrRedirection() or lpywidget.shellwidget.isSysStdErrRedirection()
    #     settings.setValue('lpyshell',to_qvariant(errinshell))
    #     settings.setValue('sysconsole',to_qvariant(errinsys))
    #     settings.endGroup()
    settings.beginGroup('syntax')
    settings.setValue('highlighted',to_qvariant(lpywidget.codeeditor.isSyntaxHighLightActivated()))
    settings.setValue('tabview',to_qvariant(lpywidget.codeeditor.isTabHighLightActivated()))
    settings.endGroup()
    settings.beginGroup('profiling')
    settings.setValue('mode',to_qvariant(lpywidget.profilingMode))
    settings.endGroup()
    if settings.status() != QSettings.NoError:
            raise Exception('settings error')
    settings.sync()
