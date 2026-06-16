from openalea.plantgl.gui.qt import qt
from openalea.plantgl.gui.qt.QtCore import QMimeData, QObject, QPoint, QRegularExpression, QTimer, Qt, Signal
from openalea.plantgl.gui.qt.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap, QSyntaxHighlighter, QTextCharFormat, QTextCursor, QTextDocument, QTextOption
from openalea.plantgl.gui.qt.QtWidgets import QLabel, QTextEdit, QWidget


# ======================================================================
# Block-state tracking (bracket nesting, production state)
# ======================================================================

class LineData:
    """Stores per-block bracket-nesting and production-state information."""
    __slots__ = ('imbricatedParanthesis', 'previousProductionState')

    def __init__(self, i=None, p=None):
        self.imbricatedParanthesis = i
        self.previousProductionState = p


class IdGenerator:
    """Recycling integer id generator used for block-state keys."""
    def __init__(self):
        self.id = 0
        self.stack = []

    def __call__(self):
        if len(self.stack) > 1:
            return self.stack.pop(0)
        else:
            i = self.id
            self.id += 1
            return i

    def release(self, i):
        self.stack.append(i)


class BlockStateTracker:
    """Manages bracket-nesting state across blocks for the highlighter.

    The highlighter delegates all ``currentBlockState`` / ``previousBlockState``
    bookkeeping and the ``linedata`` dictionary to this class so that
    ``highlightBlock`` stays focused on rule application.
    """

    def __init__(self):
        self.lineid = IdGenerator()
        self.linedata = {}

    # -- id helpers ---------------------------------------------------

    def genlineid(self):
        return (self.lineid() << 2) + 2

    def releaselinedata(self, lid):
        if lid in self.linedata:
            del self.linedata[lid]
        i = ((lid - 2) >> 2)
        self.lineid.release(i)

    # -- per-block state resolution -----------------------------------

    def resolve(self, text, highlighter):
        """Resolve the block state for *text*.

        *highlighter* is used only to call ``setCurrentBlockState``,
        ``previousBlockState``, ``setFormat`` and to read ``prodFormat``.

        Returns the previous block state (before any change) so the
        highlighter can use it for cleanup decisions.
        """
        prevst = highlighter.currentBlockState()

        if text.find('production:') >= 0:
            highlighter.setCurrentBlockState(1)
        elif text.find('endlsystem') >= 0:
            highlighter.setCurrentBlockState(0)
        elif highlighter.previousBlockState() == -1:
            highlighter.setCurrentBlockState(0)
        elif highlighter.previousBlockState() & 2:
            st = self.linedata.get(highlighter.previousBlockState(), None)
            if st is not None:
                imbricatedParanthesis = st.imbricatedParanthesis
            for i, c in enumerate(text):
                if c == '(':
                    imbricatedParanthesis += 1
                if c == ')':
                    imbricatedParanthesis -= 1
                    if imbricatedParanthesis <= 0:
                        break
            if imbricatedParanthesis <= 0:
                highlighter.setFormat(0, i, highlighter.prodFormat)
                lid = highlighter.currentBlockState()
                highlighter.setCurrentBlockState(st.previousProductionState)
            else:
                highlighter.setFormat(0, len(text), highlighter.prodFormat)
                lid = highlighter.currentBlockState()
                if lid < 0 or (lid & 2) == 0:
                    lid = self.genlineid()
                else:
                    if self.linedata[lid].imbricatedParanthesis != imbricatedParanthesis:
                        self.releaselinedata(lid)
                        lid = self.genlineid()
                self.linedata[lid] = LineData(imbricatedParanthesis, st.previousProductionState)
                highlighter.setCurrentBlockState(lid)
        else:
            highlighter.setCurrentBlockState(highlighter.previousBlockState())

        # Cleanup stale linedata from the previous state
        if prevst > 0 and (prevst & 2) and highlighter.currentBlockState() < 2:
            self.releaselinedata(prevst)

        return prevst


# ======================================================================
# Highlight rule descriptors
# ======================================================================

def _make_format(fg=None, bg=None, bold=False):
    fmt = QTextCharFormat()
    if fg is not None:
        fmt.setForeground(fg)
    if bg is not None:
        fmt.setBackground(bg)
    if bold:
        fmt.setFontWeight(QFont.Bold)
    return fmt


def _build_keyword_rules(keywords, fmt):
    """Return a list of (QRegularExpression, QTextCharFormat) for word-boundary keyword matching."""
    return [(QRegularExpression(kw), fmt) for kw in keywords]


def _build_expr_rules(patterns):
    """Return a list of (QRegularExpression, prefix_skip, QTextCharFormat, suffix_skip)."""
    return [(QRegularExpression(pat), pskip, fmt, sskip)
            for pat, pskip, fmt, sskip in patterns]


# ======================================================================
# LpySyntaxHighlighter
# ======================================================================

class LpySyntaxHighlighter(QSyntaxHighlighter):
    def __init__(self, editor):
        QSyntaxHighlighter.__init__(self, editor)

        # -- block-state tracker (extracted from inline logic) -----------
        self._tracker = BlockStateTracker()

        # -- build formats -----------------------------------------------
        self._formats = self._create_formats()

        # -- keyword lists -----------------------------------------------
        import keyword as _keyword_mod

        self.lpykeywords = [
            'Axiom:', 'production', 'homomorphism', 'interpretation',
            'decomposition', 'endlsystem', 'group', 'endgroup',
            'derivation length', 'maximum depth', 'produce', 'nproduce',
            'nsproduce', 'makestring', '-->',
            'consider:', 'ignore:', 'forward', 'backward', 'isForward', 'extern',
            'Start', 'End', 'StartEach', 'EndEach', 'getGroup', 'useGroup',
            'getIterationNb', 'module', '-static->', '@static', 'lpyimport',
            '%pastefile', '%pastemodule',
        ]
        self.pykeywords = (
            _keyword_mod.kwlist + _keyword_mod.softkwlist
            + ['None', 'range', 'xrange', 'True', 'False',
               'int', 'float', 'str', 'tuple', 'list']
        )
        self.delimiterkeywords = '[](){}+-*/:<>='

        self.prodkeywords = [
            'Axiom:', 'module', 'produce', 'nproduce', 'nsproduce',
            'makestring', '-->', '-static->', 'ignore:', 'consider:',
        ]

        # -- build rule lists from formats -------------------------------
        self.rules = (
            _build_keyword_rules(self.lpykeywords, self._formats['lpykeyword'])
            + _build_keyword_rules(self.pykeywords, self._formats['keyword'])
        )

        self.exprules = _build_expr_rules([
            # production rules: pattern, prefix_skip, format, suffix_skip
            *[(pat + '.$', len(pat), self._formats['prod'], 0) for pat in self.prodkeywords],
            # def line
            ('def[ \\t]+.*\\(', 3, self._formats['func'], 1),
            # strings
            ('"[^"]*"', 0, self._formats['string'], 0),
            ("'[^']*'", 0, self._formats['string'], 0),
            # numbers
            ('\\d+(\\.\\d+)?(e[\\+\\-]?\\d+)?', 0, self._formats['number'], 0),
        ])

        # -- tab / whitespace rules --------------------------------------
        self.tabRule = QRegularExpression("^[ \\t]+")

        # -- comment rules -----------------------------------------------
        self.commentExp = QRegularExpression('#.+$')
        self.ruleCommentExp = QRegularExpression('[ \\t]+#.+$')

        # -- lsystem rule expressions ------------------------------------
        self.lsysruleExp = [
            QRegularExpression('.+:'),
            QRegularExpression('.+\\-\\->'),
            QRegularExpression('.+\\-static\\->'),
        ]

        # -- production begin expression ---------------------------------
        self.prodbegExp = QRegularExpression('[n]produce[ \\t]*.')

        # -- state flags -------------------------------------------------
        self.setCurrentBlockState(0)
        self.activated = True
        self.tabviewactivated = True

    # ------------------------------------------------------------------
    # Format factory
    # ------------------------------------------------------------------
    @staticmethod
    def _create_formats():
        return {
            'lpykeyword': _make_format(fg=Qt.darkMagenta, bold=True),
            'keyword':    _make_format(fg=Qt.blue, bold=True),
            'delimiter':  _make_format(fg=Qt.darkBlue, bold=True),
            'prod':       _make_format(fg=Qt.black, bold=True),
            'func':       _make_format(fg=Qt.magenta),
            'string':     _make_format(fg=Qt.darkGray),
            'number':     _make_format(fg=Qt.red),
            'comment':    _make_format(fg=Qt.darkGreen),
            'tab':        _make_format(bg=QColor(220, 220, 220)),
            'space':      _make_format(bg=QColor(240, 240, 240)),
        }

    # ------------------------------------------------------------------
    # Compatibility properties (keep old attribute names working)
    # ------------------------------------------------------------------
    @property
    def lpykeywordFormat(self):  return self._formats['lpykeyword']
    @property
    def keywordFormat(self):     return self._formats['keyword']
    @property
    def delimiterFormat(self):   return self._formats['delimiter']
    @property
    def prodFormat(self):        return self._formats['prod']
    @property
    def funcFormat(self):        return self._formats['func']
    @property
    def stringFormat(self):      return self._formats['string']
    @property
    def numberFormat(self):      return self._formats['number']
    @property
    def commentFormat(self):     return self._formats['comment']
    @property
    def tabFormat(self):         return self._formats['tab']
    @property
    def spaceFormat(self):       return self._formats['space']

    # Backward-compat access to tracker internals
    @property
    def lineid(self):   return self._tracker.lineid
    @property
    def linedata(self): return self._tracker.linedata

    # ------------------------------------------------------------------
    # Public helpers (unchanged API)
    # ------------------------------------------------------------------
    def setDocument(self, doc):
        QSyntaxHighlighter.setDocument(self, doc)

    def genlineid(self):
        return self._tracker.genlineid()

    def releaselinedata(self, lid):
        self._tracker.releaselinedata(lid)

    def setActivation(self, value):
        self.activated = value
        self.rehighlight()

    def setTabViewActivation(self, value):
        self.tabviewactivated = value
        self.rehighlight()

    # ------------------------------------------------------------------
    # highlightBlock – now decomposed into small focused steps
    # ------------------------------------------------------------------
    def highlightBlock(self, text):
        text = str(text)
        if not self.activated:
            return

        lentxt = len(text)

        # 1. Block-state tracking (delegated to tracker)
        prevst = self._tracker.resolve(text, self)

        # 2. Delimiter highlighting
        self._apply_delimiters(text)

        # 3. L-system rule highlighting (only inside production blocks)
        self._apply_lsys_rules(text, lentxt)

        # 4. Keyword rules
        self._apply_keyword_rules(text, lentxt)

        # 5. Extended rules (productions, def, strings, numbers)
        self._apply_expr_rules(text, lentxt, prevst)

        # 6. Tab / whitespace highlighting
        if self.tabviewactivated:
            self._apply_tab_highlight(text)

        # 7. Comments
        self._apply_comments(text)

    # ------------------------------------------------------------------
    # Individual highlight steps
    # ------------------------------------------------------------------
    def _apply_delimiters(self, text):
        fmt = self._formats['delimiter']
        for i, c in enumerate(text):
            if c in self.delimiterkeywords:
                self.setFormat(i, 1, fmt)

    def _apply_lsys_rules(self, text, lentxt):
        if self.currentBlockState() != 1:
            return
        if lentxt <= 0 or text[0] in " \t":
            return
        for ruleExp in self.lsysruleExp:
            match = ruleExp.match(text)
            index = match.capturedStart()
            if index >= 0:
                length = match.capturedLength()
                self.setFormat(index, length, self._formats['prod'])
                break

    def _apply_keyword_rules(self, text, lentxt):
        for expression, fmt in self.rules:
            matches = expression.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                index = match.capturedStart()
                index_end = match.capturedEnd()
                length = match.capturedLength()
                if ((index == 0 or not text[index - 1].isalnum()) and
                        (index_end == lentxt or not text[index_end].isalnum())):
                    self.setFormat(index, length, fmt)

    def _apply_expr_rules(self, text, lentxt, prevst):
        for expression, prefix_skip, fmt, suffix_skip in self.exprules:
            matches = expression.globalMatch(text)
            while matches.hasNext():
                match = matches.next()
                index = match.capturedStart()
                index_end = match.capturedEnd()
                length = index_end - index
                if index == 0 or not text[index - 1].isalnum():
                    self.setFormat(index + prefix_skip, length - prefix_skip - suffix_skip, fmt)
                    mt = match.capturedTexts()[0]
                    ei_m = self.prodbegExp.match(mt)
                    ei = ei_m.capturedStart()
                    if ei >= 0 and str(ei_m.captured(0))[-1] == '(':
                        previousProductionState = self.previousBlockState()
                        imbricatedParanthesis = 1
                        for c in mt[ei_m.capturedEnd() + 1:]:
                            if c == '(':
                                imbricatedParanthesis += 1
                            if c == ')':
                                imbricatedParanthesis -= 1
                                if imbricatedParanthesis <= 0:
                                    self.setCurrentBlockState(previousProductionState)
                                    break
                        if imbricatedParanthesis > 0:
                            lid = self.genlineid()
                            self.setCurrentBlockState(lid)
                            self._tracker.linedata[lid] = LineData(imbricatedParanthesis, previousProductionState)

    def _apply_tab_highlight(self, text):
        match = self.tabRule.match(text)
        index = match.capturedStart()
        if index >= 0:
            end_m = match.capturedEnd()
            tab_fmt = self._formats['tab']
            space_fmt = self._formats['space']
            for i in range(index, end_m):
                if text[i] == '\t':
                    self.setFormat(i, 1, tab_fmt)
                else:
                    self.setFormat(i, 1, space_fmt)

    def _apply_comments(self, text):
        commentExp = self.commentExp
        matches = commentExp.globalMatch(text)
        comment_fmt = self._formats['comment']
        while matches.hasNext():
            m = matches.next()
            index = m.capturedStart()
            length = m.capturedEnd()
            self.setFormat(index, length, comment_fmt)


# ======================================================================
# Margin (line numbers + markers) – unchanged
# ======================================================================

class Margin(QWidget):

    lineClicked = Signal(int)

    def __init__(self,parent,editor):
        QWidget.__init__(self,parent)
        self.editor = editor
        self.showLines = True
        self.markers = {}
        self.markerStack = {}
        self.markerType = {}

    def paintEvent( self, paintEvent ):
        if self.showLines:
            maxheight = self.editor.viewport().height()
            maxline = self.editor.document().blockCount()
            painter = QPainter(self)
            painter.setPen(QPen(QColor(100,100,100)))
            h = 0
            line = -1
            while h < maxheight and line < maxline:
                cursor = self.editor.cursorForPosition(QPoint(1,h))
                nline = cursor.blockNumber()+1
                rect = self.editor.cursorRect(cursor)
                if nline > line:
                    line = nline
                    painter.drawText(0,rect.top()+2,40,rect.height()+2, Qt.AlignHCenter|Qt.AlignTop,str(line))
                    m = self.markers.get(line,None)
                    if not m is None:
                        lm = self.markerStack.get(line,None)
                        if not lm is None:
                            for slm in lm:
                                painter.drawPixmap(32,rect.top()+2,self.markerType[slm])
                        painter.drawPixmap(32,rect.top()+2,self.markerType[m])
                h = rect.top()+rect.height()+1
            painter.end()

    def mousePressEvent( self, event ):
        line = self.editor.cursorForPosition(event.pos()).blockNumber()
        self.lineClicked.emit(line+1)
    def clear( self ):
        self.removeAllMarkers()
        self.markerType = {}
    def hasMarker(self):
        return len(self.markers) != 0
    def setMarkerAt(self,line,id):
        self.markers[line] = id
        if line in self.markerStack:
            del self.markerStack[line]
        self.update()
    def hasMarkerAt(self,line):
        return line in self.markers
    def hasMarkerTypeAt(self,line,id):
        if line in self.markers :
            if self.markers[line] == id: return True
            if line in self.markerStack:
                if id in self.markerStack[line]:
                    return True
        return False
    def getCurrentMarkerAt(self,line):
        return self.markers[line]
    def removeCurrentMarkerAt(self,line):
        del self.markers[line]
        if line in self.markerStack:
            self.markers[line] = self.markerStack[line].pop()
            if len(self.markerStack[line]) == 0:
                del self.markerStack[line]
        self.update()
    def removeMarkerTypeAt(self,line,id):
        if self.markers[line] == id:
            self.removeCurrentMarkerAt(line)
        else:
            self.markerStack[line].remove(id)
            if len(self.markerStack[line]) == 0:
                del self.markerStack[line]
        self.update()
    def removeAllMarkersAt(self,line):
        if line in self.marker:
            del self.markers[line]
        if line in self.markerStack:
            del self.markerStack[line]
        self.update()
    def removeAllMarkers(self):
        self.markers = {}
        self.markerStack = {}
        self.update()
    def addMarkerAt(self,line,id):
        val = self.markers.get(line,None)
        if not val is None:
            if line not in self.markerStack:
                self.markerStack[line] = []
            self.markerStack[line].append(val)
        self.markers[line] = id
        self.update()
    def appendMarkerAt(self,line,id):
        val = self.markers.get(line,None)
        if not val is None:
            if line not in self.markerStack:
                self.markerStack[line] = []
            self.markerStack[line].append(id)
        else:
            self.markers[line] = id
        self.update()
    def defineMarker(self,id,pixmap):
        self.markerType[id] = pixmap
    def getAllMarkers(self,id):
        return set([l for l,lid in self.markers.items() if id == lid]).union(set([l for l,lids in self.markerStack.items() if id in lids]))
    def decalMarkers(self,line,decal = 1):
        markers = {}
        markerStack = {}
        if decal < 0:
          for l,v in self.markers.items():
            if l <= line+decal:
                markers[l] = v
            elif l > line:
                markers[l+decal] = v
          for l,v in self.markerStack.items():
            if l <= line+decal:
                markerStack[l] = v
            elif l > line:
                markerStack[l+decal] = v
        if decal > 0:
          for l,v in self.markers.items():
            if l < line:
                markers[l] = v
            else:
                markers[l+decal] = v
          for l,v in self.markerStack.items():
            if l < line:
                markerStack[l] = v
            else:
                markerStack[l+decal] = v
        if decal != 0:
            self.markers = markers
            self.markerStack = markerStack
            self.update()
    def saveState(self,obj):
        obj.markersState = (self.markers,self.markerStack)
    def restoreState(self,obj):
        if hasattr(obj,'markersState'):
            self.markers,self.markerStack = obj.markersState
        else:
            self.removeAllMarkers()

ErrorMarker,BreakPointMarker,CodePointMarker = list(range(3))


# ======================================================================
# LpyCodeEditor – unchanged (only highlighter interaction is via public API)
# ======================================================================

class LpyCodeEditor(QTextEdit):
    def __init__(self,parent):
        QTextEdit.__init__(self,parent)
        self.editor = None
        self.setAcceptDrops(True)
        self.setWordWrapMode(QTextOption.WrapAnywhere)
        self.findEdit = None
        self.gotoEdit = None
        self.matchCaseButton = None
        self.wholeWordButton = None
        self.nextButton = None
        self.previousButton = None
        self.replaceEdit = None
        self.replaceButton = None
        self.replaceAllButton = None
        self.replaceTab = True
        self.indentation = '  '
        self.hasError = False
        self.defaultdoc = self.document().clone()
        self.setDocument(self.defaultdoc)
        self.syntaxhighlighter = LpySyntaxHighlighter(self)
        self.zoomFactor = 0
        self.editionFont = None
    def initWithEditor(self,lpyeditor):
        self.editor = lpyeditor
        self.findEdit = lpyeditor.findEdit
        self.frameFind = lpyeditor.frameFind
        self.gotoEdit = lpyeditor.gotoEdit
        self.matchCaseButton = lpyeditor.matchCaseButton
        self.wholeWordButton = lpyeditor.wholeWordButton
        self.nextButton = lpyeditor.findNextButton
        self.previousButton = lpyeditor.findPreviousButton
        self.replaceEdit = lpyeditor.replaceEdit
        self.replaceButton = lpyeditor.replaceButton
        self.replaceAllButton = lpyeditor.replaceAllButton
        self.statusBar = lpyeditor.statusBar()
        self.positionLabel = QLabel(self.statusBar)
        self.statusBar.addPermanentWidget(self.positionLabel)
        self.findEdit.textEdited.connect(self.findText)

        lpyeditor.actionFind.triggered.connect(self.focusFind)
        self.findEdit.returnPressed.connect(self.setFocus)
        self.gotoEdit.returnPressed.connect(self.gotoLineFromEdit)
        self.gotoEdit.returnPressed.connect(self.setFocus)
        self.previousButton.pressed.connect(self.findPreviousText)
        self.nextButton.pressed.connect(self.findNextText)
        self.replaceButton.pressed.connect(self.replaceText)
        self.replaceAllButton.pressed.connect(self.replaceAllText)
        self.cursorPositionChanged.connect(self.printCursorPosition)
        lpyeditor.actionZoomIn.triggered.connect(self.zoomInEvent)
        lpyeditor.actionZoomOut.triggered.connect(self.zoomOutEvent)
        lpyeditor.actionNoZoom.triggered.connect(self.resetZoom)
        lpyeditor.actionGoto.triggered.connect(self.setLineInEdit)

        self.defaultEditionFont = self.currentFont()
        self.defaultPointSize = self.currentFont().pointSize()
        self.setViewportMargins(50,0,0,0)
        self.sidebar = Margin(self,self)
        self.sidebar.setGeometry(0,0,50,100)
        self.sidebar.defineMarker(ErrorMarker,QPixmap(':/images/icons/warningsErrors16.png'))
        self.sidebar.defineMarker(BreakPointMarker,QPixmap(':/images/icons/BreakPoint.png'))
        self.sidebar.defineMarker(CodePointMarker,QPixmap(':/images/icons/greenarrow16.png'))
        self.sidebar.show()
        self.sidebar.lineClicked.connect(self.checkLine)
    def checkLine(self,line):
        self.statusBar.showMessage("Line "+str(line)+" clicked",2000)
        if self.sidebar.hasMarkerAt(line):
            if self.hasError and self.errorLine == line:
                self.clearErrorHightlight()
            elif self.sidebar.hasMarkerTypeAt(line,BreakPointMarker):
                self.sidebar.removeMarkerTypeAt(line,BreakPointMarker)
            else:
                self.sidebar.appendMarkerAt(line,BreakPointMarker)
        else:
            self.sidebar.setMarkerAt(line,BreakPointMarker)
    def resizeEvent(self,event):
        self.sidebar.setGeometry(0,0,48,self.height())
        QTextEdit.resizeEvent(self,event)
    def scrollContentsBy(self,dx,dy):
        self.sidebar.update()
        self.sidebar.setFont(QFont(self.currentFont()))
        QTextEdit.scrollContentsBy(self,dx,dy)
    def focusInEvent ( self, event ):
        if self.editor : self.editor.currentSimulation().monitorfile()
        return QTextEdit.focusInEvent ( self, event )
    def setReplaceTab(self,value):
        self.replaceTab = value
    def tabSize(self):
        return len(self.indentation)
    def setTabSize(self, value):
        assert value > 0
        self.indentation = ' '*value
        self.setTabStopWidth(value*self.currentFont().pointSize())
    def setLpyDocument(self,document):
        self.syntaxhighlighter.setDocument(document)
        LpyCodeEditor.setDocument(self,document)
        self.syntaxhighlighter.rehighlight()
        self.applyZoom()
        if not self.editionFont is None and self.editionFont!= document.defaultFont() :
            document.setDefaultFont(self.editionFont)
    def zoomInEvent(self):
        self.zoomFactor += 1
        self.zoomIn()
    def zoomOutEvent(self):
        self.zoomFactor -= 1
        self.zoomOut()
    def resetZoom(self):
        if self.zoomFactor > 0:
            self.zoomOut(self.zoomFactor)
        elif self.zoomFactor < 0:
            self.zoomIn(-self.zoomFactor)
        self.zoomFactor = 0
    def applyZoom(self):
        self.zoomIn()
        self.zoomOut()
    def printCursorPosition(self):
        cursor = self.textCursor()
        self.positionLabel.setText('Line '+str(cursor.blockNumber()+1)+', Column '+str(cursor.columnNumber())+' ('+str(cursor.position())+')')
    def keyPressEvent(self,event):
        if self.hasError:
            self.clearErrorHightlight()
        lcursor = self.textCursor()
        bbn = lcursor.blockNumber()
        if lcursor.selectionStart() == lcursor.selectionEnd() and (event.key() == Qt.Key_Delete or event.key() == Qt.Key_Backspace):
            if event.key() == Qt.Key_Backspace:
                lcursor.movePosition(QTextCursor.PreviousCharacter,QTextCursor.KeepAnchor)
            else:
                lcursor.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
        if event.key() == Qt.Key_Tab and lcursor.hasSelection():
            if event.modifiers() == Qt.NoModifier:
                self.tab()
            else:
                self.untab()
        else:
            seltxt = lcursor.selection().toPlainText()
            sbn = seltxt.count('\n')
            rev = self.document().revision()
            QTextEdit.keyPressEvent(self,event)
            if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                self.returnEvent()
                sbn -=1
            elif event.key() == Qt.Key_Tab :
                self.tabEvent()
            if rev != self.document().revision():
                self.sidebar.decalMarkers(bbn+sbn,-sbn)
    def returnEvent(self):
        cursor = self.textCursor()
        beg = cursor.selectionStart()
        end = cursor.selectionEnd()
        if beg == end:
            pos = cursor.position()
            ok = cursor.movePosition(QTextCursor.PreviousBlock,QTextCursor.MoveAnchor)
            if not ok: return
            txtok = True
            txt = ''
            while txtok:
                ok = cursor.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
                if not ok: break
                txt2 = str(cursor.selection().toPlainText())
                txtok = (txt2[-1] in ' \t')
                if txtok:
                    txt = txt2
            cursor.setPosition(pos)
            ok = cursor.movePosition(QTextCursor.PreviousBlock,QTextCursor.MoveAnchor)
            if ok:
                ok = cursor.movePosition(QTextCursor.EndOfBlock,QTextCursor.MoveAnchor)
                if ok:
                    txtok = True
                    while txtok:
                        ok = cursor.movePosition(QTextCursor.PreviousCharacter,QTextCursor.KeepAnchor)
                        if not ok: break
                        txt2 = str(cursor.selection().toPlainText())
                        txtok = (txt2[0] in ' \t')
                        if not txtok:
                            if txt2[0] == ':':
                                txt += self.indentation
            cursor.setPosition(pos)
            cursor.joinPreviousEditBlock()
            cursor.insertText(txt)
            cursor.endEditBlock()
    def tabEvent(self):
        if self.replaceTab:
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.joinPreviousEditBlock()
                cursor.deletePreviousChar()
                self.tab(cursor)
                cursor.endEditBlock()
            else:
                cursor.joinPreviousEditBlock()
                cursor.deletePreviousChar()
                cursor.insertText(self.indentation)
                cursor.endEditBlock()
    def getFindOptions(self):
        options = QTextDocument.FindFlags()
        if self.matchCaseButton.isChecked():
            options |= QTextDocument.FindCaseSensitively
        if self.wholeWordButton.isChecked():
            options |= QTextDocument.FindWholeWords
        return options
    def cursorAtStart(self):
        cursor = self.textCursor()
        cursor.setPosition(0,QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)
    def focusFind(self):
        if not self.frameFind.isVisible():
            self.setfindEditColor(QColor(255,255,255))
            self.frameFind.show()
            cursor = self.textCursor()
            if cursor.hasSelection() :
                self.findEdit.setText(cursor.selectedText())
            self.findEdit.selectAll()
            self.findEdit.setFocus()
        else:
            cursor = self.textCursor()
            if not cursor.hasSelection() or cursor.selectedText() == self.findEdit.text():
                self.findNextText()
            elif cursor.hasSelection():
                self.findEdit.setText(cursor.selectedText())
                self.findEdit.selectAll()
                self.findEdit.setFocus()

    def findNextText(self):
        txt = self.findEdit.text()
        found = self.find(txt,self.getFindOptions())
        if found:
            self.setFocus()
            self.setfindEditColor(QColor(255,255,255))
        else:
            self.findEndOFFile()
            self.cursorAtStart()
            self.setfindEditColor(QColor(255,100,100))
    def setfindEditColor(self,color):
        palette = self.findEdit.palette()
        palette.setColor(QPalette.Base,color)
        self.findEdit.setPalette(palette)
    def findEndOFFile(self):
            q = QLabel('Text not found !')
            q.setPixmap(QPixmap(':/images/icons/wrap.png'))
            self.statusBar.addWidget(q)
            self.statusBar.showMessage('     End of page found, restart from top !',2000)
            QTimer.singleShot(2000,lambda : self.statusBar.removeWidget(q))
    def findPreviousText(self):
        txt = self.findEdit.text()
        found = self.find(txt,QTextDocument.FindBackward|self.getFindOptions())
        if found:
            self.setFocus()
        else:

            self.findEndOFFile()
            self.cursorAtStart()
    def findText(self,txt):
        cursor = self.textCursor()
        cursor.setPosition(0,QTextCursor.MoveAnchor)
        self.setTextCursor(cursor)
        self.find(txt,self.getFindOptions())
    def replaceText(self):
        txt = self.findEdit.text()
        cursor = self.textCursor()
        if cursor.selectedText() == txt:
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(self.replaceEdit.text())
            cursor.endEditBlock()
            self.find(txt,self.getFindOptions())
        else:
            self.findNextText()
    def replaceAllText(self):
        txt = self.findEdit.text()
        cursor = self.textCursor()
        if cursor.selectedText() == txt:
            nboccurrence = 1
            cursor.beginEditBlock()
            cursor.removeSelectedText()
            cursor.insertText(self.replaceEdit.text())
            found = self.find(txt,self.getFindOptions())
            while found :
                nboccurrence += 1
                cursor = self.textCursor()
                cursor.removeSelectedText()
                cursor.insertText(self.replaceEdit.text())
                found = self.find(txt,self.getFindOptions())
            cursor.endEditBlock()
            self.statusBar.showMessage('Replace '+str(nboccurrence)+' occurrences.',5000)
            self.cursorAtStart()
        else:
            self.findNextText()
    def setSyntaxHighLightActivation(self,value):
        self.syntaxhighlighter.setActivation(value)
    def isSyntaxHighLightActivated(self):
        return self.syntaxhighlighter.activated
    def setTabHighLightActivation(self,value):
        self.syntaxhighlighter.setTabViewActivation(value)
    def isTabHighLightActivated(self):
        return self.syntaxhighlighter.tabviewactivated
    def canInsertFromMimeData(self,source):
        if source.hasUrls():
            return True
        else: return source.hasText()
    def insertFromMimeData(self,source):
        if source.hasUrls():
            if not self.editor is None:
                url = source.urls()[0]
                if len(url.host()) == 0 and url.path().startswith("/.file/id="):
                    import os
                    cmd = """osascript -e 'get posix path of posix file "{}" -- kthxbai'""".format(url.path())
                    path = os.popen(cmd).read().strip()
                else:
                    path = url.toLocalFile()
                self.editor.openfile(path)
        else :
            nsource = QMimeData()
            nsource.setText(source.text())
            return QTextEdit.insertFromMimeData(self,nsource)
    def comment(self):
        cursor = self.textCursor()
        beg = cursor.selectionStart()
        end = cursor.selectionEnd()
        pos = cursor.position()
        cursor.beginEditBlock()
        cursor.setPosition(beg,QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.StartOfBlock,QTextCursor.MoveAnchor)
        while cursor.position() <= end:
            cursor.insertText('#')
            oldpos = cursor.position()
            cursor.movePosition(QTextCursor.NextBlock,QTextCursor.MoveAnchor)
            if cursor.position() == oldpos:
                break
            end+=1
        cursor.endEditBlock()
        cursor.setPosition(pos,QTextCursor.MoveAnchor)
    def uncomment(self):
        cursor = self.textCursor()
        beg = cursor.selectionStart()
        end = cursor.selectionEnd()
        pos = cursor.position()
        cursor.beginEditBlock()
        cursor.setPosition(beg,QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.StartOfBlock,QTextCursor.MoveAnchor)
        while cursor.position() <= end:
            m = cursor.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
            if True:
                if cursor.selectedText() == '#':
                        cursor.deleteChar()
                end-=1
            cursor.movePosition(QTextCursor.Down,QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.Left,QTextCursor.MoveAnchor)
        cursor.endEditBlock()
        cursor.setPosition(pos,QTextCursor.MoveAnchor)
    def tab(self, initcursor = None):
        if initcursor == False:
            initcursor = None
        cursor = self.textCursor() if initcursor is None else initcursor
        beg = cursor.selectionStart()
        end = cursor.selectionEnd()
        pos = cursor.position()
        if not initcursor : cursor.beginEditBlock()
        cursor.setPosition(beg,QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.StartOfBlock,QTextCursor.MoveAnchor)
        while cursor.position() <= end :
            if self.replaceTab:
                cursor.insertText(self.indentation)
                end+=len(self.indentation)
            else:
                cursor.insertText('\t')
                end+=1
            oldpos = cursor.position()
            cursor.movePosition(QTextCursor.NextBlock,QTextCursor.MoveAnchor)
            if cursor.position() == oldpos:
                break
        if not initcursor : cursor.endEditBlock()
        cursor.setPosition(pos,QTextCursor.MoveAnchor)
    def untab(self):
        cursor = self.textCursor()
        beg = cursor.selectionStart()
        end = cursor.selectionEnd()
        pos = cursor.position()
        cursor.beginEditBlock()
        cursor.setPosition(beg,QTextCursor.MoveAnchor)
        cursor.movePosition(QTextCursor.StartOfBlock,QTextCursor.MoveAnchor)
        while cursor.position() <= end:
            m = cursor.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
            if cursor.selectedText() == '\t':
                cursor.deleteChar()
            else:
                for i in range(len(self.indentation)-1):
                    b = cursor.movePosition(QTextCursor.NextCharacter,QTextCursor.KeepAnchor)
                    if not b : break
                if cursor.selectedText() == self.indentation:
                    cursor.removeSelectedText()
            end-=1
            cursor.movePosition(QTextCursor.Down,QTextCursor.MoveAnchor)
            cursor.movePosition(QTextCursor.StartOfBlock,QTextCursor.MoveAnchor)
        cursor.endEditBlock()
        cursor.setPosition(pos,QTextCursor.MoveAnchor)
    def hightlightError(self,lineno):
        if self.editor : self.editor.textEditionWatch = False
        if self.hasError:
            self.clearErrorHightlight()
        if lineno < self.document().lineCount() :
            self.sidebar.addMarkerAt(lineno,ErrorMarker)
            self.errorLine = lineno
            cursor = self.textCursor()
            cursor.setPosition(0)
            cursor.movePosition(QTextCursor.NextBlock,QTextCursor.MoveAnchor,lineno-1)
            cursor.movePosition(QTextCursor.EndOfBlock,QTextCursor.KeepAnchor)
            errorformat = QTextCharFormat()
            errorformat.setBackground(Qt.yellow)
            cursor.setCharFormat(errorformat)
            self.gotoLine(lineno)
            self.hasError = True
        if self.editor : self.editor.textEditionWatch = True
    def clearErrorHightlight(self):
        cursor = self.textCursor()
        self.undo()
        self.setTextCursor(cursor)
        self.hasError = False
        self.sidebar.removeCurrentMarkerAt(self.errorLine)
    def setEditionFontFamily(self,font):
        font.setPointSize( self.currentFont().pointSize() )
        self.setEditionFont(font)
    def setEditionFontSize(self,p):
        f = self.editionFont
        if self.editionFont is None:
            f = QFont(self.defaultEditionFont)
        f.setPointSize( p )
        self.setEditionFont(f)
    def setEditionFont(self,font):
        self.editionFont = font
        self.document().setDefaultFont(font)
    def isFontToDefault(self):
        if self.editionFont is None : return True
        return str(self.editionFont.family()) == str(self.defaultEditionFont.family()) and self.editionFont.pointSize() == self.defaultEditionFont.pointSize()
    def gotoLine(self,lineno):
        cursor = self.textCursor()
        cursor.setPosition(0)
        cursor.movePosition(QTextCursor.NextBlock,QTextCursor.MoveAnchor,lineno-1)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    def gotoLineFromEdit(self):
        self.gotoLine(int(self.gotoEdit.text()))
    def setLineInEdit(self):
        self.gotoEdit.setText(str(self.textCursor().blockNumber()+1))
        self.gotoEdit.selectAll()
    def restoreSimuState(self,simu):
        if self.hasError:
            self.clearErrorHightlight()
        firstinit = simu.textdocument is None
        if firstinit:
            simu.textdocument = self.document().clone()
        self.setLpyDocument(simu.textdocument)
        if firstinit:
            self.clear()
            self.setText(simu.code)
        if not simu.cursor is None:
            self.setTextCursor(simu.cursor)
            self.horizontalScrollBar().setValue(simu.hvalue)
            self.verticalScrollBar().setValue(simu.vvalue)
        self.sidebar.restoreState(simu)
    def saveSimuState(self,simu):
        simu.code = self.getCode()
        if simu.textdocument is None:
            print('custom document clone')
            simu.textdocument = self.document().clone()
        simu.cursor = self.textCursor()
        simu.hvalue = self.horizontalScrollBar().value()
        simu.vvalue = self.verticalScrollBar().value()
        self.sidebar.saveState(simu)

    def getCode(self):
        return str(self.toPlainText()).encode('iso-8859-1','replace').decode('iso-8859-1')

    def codeToExecute(self):
        cursor = self.textCursor()
        curpos = cursor.position()
        selbegin = cursor.selectionStart()
        selend   = cursor.selectionEnd()
        cursor.setPosition(selbegin)
        cursor.movePosition(QTextCursor.StartOfLine)
        cursor.setPosition(selend, QTextCursor.KeepAnchor)
        cursor.movePosition(QTextCursor.EndOfLine, QTextCursor.KeepAnchor)
        cmd = cursor.selectedText()
        if False : #len(cmd) > 0:
            lines = cmd.splitlines()
            fline = lines[0]
            nfline = fline.lstrip()
            torem = len(fline) - len(nfline)
            nlines = [l[torem:] for l in lines]
            cmd = '\n'.join(nlines)
        return cmd
