"""
Tests for the session_io module (session export/import).

These tests exercise the JSON serialisation helpers *without* requiring a
running Qt application.  They mock out the simulation and widget objects
just enough to verify round-trip correctness.
"""

import json
import os
import sys
import tempfile
import unittest

# Ensure the source tree is on sys.path so we can import without installation
_SRC = os.path.join(os.path.dirname(__file__), os.pardir, 'src')
if os.path.isdir(_SRC):
    sys.path.insert(0, os.path.abspath(_SRC))


# ---------------------------------------------------------------------------
# Helpers / lightweight mocks
# ---------------------------------------------------------------------------

class _FakeModuleMonitor:
    def __init__(self):
        self.modules = set()
        self.sysmodules = {}


class _FakeContext:
    class _Turtle:
        def getColorList(self):
            return []
        def setMaterial(self, *a):
            pass
    class _Options:
        selection = 0
        def __len__(self):
            return 0
    def __init__(self):
        self.turtle = self._Turtle()
        self.options = self._Options()
        self.animation_timestep = 0.05


class _FakeLsystem:
    def __init__(self):
        self.derivationLength = 5
        self._ctx = _FakeContext()
    def context(self):
        return self._ctx


class _FakeTabBar:
    def setTabText(self, *a):
        pass
    def setTabIcon(self, *a):
        pass
    def currentIndex(self):
        return 0


class _FakeScalarEditor:
    def __init__(self):
        self._scalars = []
    def getScalars(self):
        return self._scalars
    def setScalars(self, v):
        self._scalars = list(v)


class _FakeCodeEditor:
    def __init__(self, code=''):
        self._code = code
    def getCode(self):
        return self._code
    def saveSimuState(self, sim):
        sim.code = self._code
    def restoreSimuState(self, sim):
        pass


class _FakePanel:
    def __init__(self, info, objects):
        self.info = info
        self.objects = objects
        self.name = info.get('name', 'Panel')
    def getInfo(self):
        return self.info
    def getObjects(self):
        return self.objects
    def setInfo(self, info):
        self.info = info
    def setObjects(self, objects):
        self.objects = objects


class _FakeDescEditor:
    def __init__(self, text=''):
        self._text = text
    def text(self):
        return self._text
    def toPlainText(self):
        return self._text
    def setText(self, v):
        self._text = v


class _FakeWidget:
    """Minimal stand-in for ``LPyWindow``."""
    def __init__(self):
        self.documentNames = _FakeTabBar()
        self.codeeditor = _FakeCodeEditor('Axiom: A\nderivation length: 5\nproduction:\nA -> AB\n\nendlsystem\n')
        self.scalarEditor = _FakeScalarEditor()
        self.materialed = type('M', (), {'setTurtle': lambda self, t: None, 'setEnabled': lambda self, v: None})()
        self.parametersTable = type('P', (), {'setModel': lambda s, m: None, 'setItemDelegateForColumn': lambda s, c, d: None, 'setEnabled': lambda s, v: None})()
        self.desc_items = {
            '__authors__': _FakeDescEditor('Test Author'),
            '__institutes__': _FakeDescEditor('Test Institute'),
            '__copyright__': _FakeDescEditor(''),
            '__description__': _FakeDescEditor('A test simulation'),
            '__references__': _FakeDescEditor(''),
        }
        self.currentSimulationId = 0
        self.simulations = []
        self._panels = []
        self.interpreter = None
        self.showPyCode = False
    def getObjectPanels(self):
        return self._panels
    def setObjectPanelNb(self, n, *a):
        pass
    def setTimeStep(self, v):
        pass
    def printTitle(self):
        pass
    def statusBar(self):
        return type('S', (), {'showMessage': lambda s, m, t=0: None})()


class _FakeSimulation:
    """Minimal simulation mock sufficient for export."""
    def __init__(self, widget):
        self.lpywidget = widget
        self.lsystem = _FakeLsystem()
        self.fname = None
        self.code = widget.codeeditor.getCode()
        self.desc_items = {k: v.text() for k, v in widget.desc_items.items()}
        self.scalars = widget.scalarEditor.getScalars()
        self.visualparameters = [({'name': 'Panel 1', 'active': True}, [])]
        self.modulemonitor = _FakeModuleMonitor()
        self.textedition = False
        self._edited = False
    def isCurrent(self):
        return True
    def saveState(self):
        pass
    def getShortName(self):
        return 'New'
    def restoreState(self):
        pass
    def registerTab(self):
        pass
    def setFname(self, f):
        self.fname = f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSessionIO(unittest.TestCase):
    """Round-trip tests for session_io."""

    def _get_session_io(self):
        # Import lazily to allow skipping when dependencies are missing
        try:
            from openalea.lpy.gui import session_io
            return session_io
        except ImportError:
            # If the full openalea stack is not installed we fall back to
            # a direct import of the module file.
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                'session_io',
                os.path.join(os.path.dirname(__file__), os.pardir, 'src',
                             'openalea', 'lpy', 'gui', 'session_io.py'),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

    # -- export ---------------------------------------------------------------

    def test_export_basic_structure(self):
        session_io = self._get_session_io()
        widget = _FakeWidget()
        sim = _FakeSimulation(widget)
        data = session_io.export_simulation_to_dict(sim)

        self.assertEqual(data['format'], 'lpysession')
        self.assertEqual(data['version'], session_io.SESSION_FORMAT_VERSION)
        self.assertIn('code', data)
        self.assertIn('Axiom', data['code'])
        self.assertEqual(data['derivation_length'], 5)
        self.assertEqual(data['desc_items']['__authors__'], 'Test Author')
        self.assertEqual(data['desc_items']['__description__'], 'A test simulation')
        self.assertEqual(data['panels'], [{'info': {'name': 'Panel 1', 'active': True}, 'objects': []}])
        self.assertEqual(data['scalars'], [])
        self.assertEqual(data['module_files'], [])
        self.assertIsNone(data['source_file'])

    def test_export_to_file_roundtrip(self):
        session_io = self._get_session_io()
        widget = _FakeWidget()
        sim = _FakeSimulation(widget)
        with tempfile.NamedTemporaryFile('w', suffix='.lpysession', delete=False) as fh:
            fname = fh.name
        try:
            session_io.export_simulation_to_file(sim, fname)
            with open(fname, 'r') as fh:
                data = json.load(fh)
            self.assertEqual(data['format'], 'lpysession')
            self.assertIn('Axiom', data['code'])
        finally:
            os.unlink(fname)

    # -- scalars --------------------------------------------------------------

    def test_scalar_rebuild_integer(self):
        session_io = self._get_session_io()
        raw = {'name': 'n', 'value': 10, 'min': 0, 'max': 50, 'type': 'Integer'}
        # The _rebuild_scalar function imports from lsysparameters; if not
        # installed this is skipped.
        try:
            sc = session_io._rebuild_scalar(raw)
            self.assertEqual(sc.name, 'n')
            self.assertEqual(sc.value, 10)
        except ImportError:
            self.skipTest('lsysparameters not installed')

    def test_scalar_rebuild_tuple_fallback(self):
        session_io = self._get_session_io()
        raw = {'__tuple__': ('x', 'Float', 1.5, 0.0, 10.0, 2)}
        try:
            sc = session_io._rebuild_scalar(raw)
            self.assertEqual(sc.name, 'x')
            self.assertAlmostEqual(sc.value, 1.5)
        except ImportError:
            self.skipTest('lsysparameters not installed')

    def test_scalar_rebuild_bool(self):
        session_io = self._get_session_io()
        raw = {'name': 'flag', 'value': True, 'type': 'Bool'}
        try:
            sc = session_io._rebuild_scalar(raw)
            self.assertTrue(sc.isBool())
            self.assertTrue(sc.value)
        except ImportError:
            self.skipTest('lsysparameters not installed')

    def test_scalar_rebuild_category(self):
        session_io = self._get_session_io()
        raw = {'name': 'group A', 'type': 'Category'}
        try:
            sc = session_io._rebuild_scalar(raw)
            self.assertTrue(sc.isCategory())
        except ImportError:
            self.skipTest('lsysparameters not installed')

    # -- merge ----------------------------------------------------------------

    def test_merge_sessions(self):
        session_io = self._get_session_io()
        s1 = {
            'format': 'lpysession',
            'version': session_io.SESSION_FORMAT_VERSION,
            'code': 'Axiom: A\n',
            'derivation_length': 3,
            'desc_items': {'__authors__': 'A'},
            'scalars': [],
            'panels': [{'info': {'name': 'P1'}, 'objects': []}],
            'module_files': ['mod1.py'],
            'materials': [],
        }
        s2 = dict(s1)
        s2['panels'] = [{'info': {'name': 'P2'}, 'objects': []}]
        s2['module_files'] = ['mod2.py']

        with tempfile.NamedTemporaryFile('w', suffix='.lpysession', delete=False) as f1:
            json.dump(s1, f1)
            f1_name = f1.name
        with tempfile.NamedTemporaryFile('w', suffix='.lpysession', delete=False) as f2:
            json.dump(s2, f2)
            f2_name = f2.name
        out_name = f1_name + '.merged.lpysession'
        try:
            session_io.merge_sessions([f1_name, f2_name], out_name)
            with open(out_name) as fh:
                merged = json.load(fh)
            self.assertEqual(len(merged['panels']), 2)
            self.assertEqual(merged['panels'][0]['info']['name'], 'P1')
            self.assertEqual(merged['panels'][1]['info']['name'], 'P2')
            self.assertEqual(merged['module_files'], ['mod1.py', 'mod2.py'])
            self.assertEqual(merged['code'], 'Axiom: A\n')
        finally:
            for n in (f1_name, f2_name, out_name):
                if os.path.exists(n):
                    os.unlink(n)

    def test_merge_sessions_no_input_raises(self):
        session_io = self._get_session_io()
        with self.assertRaises(ValueError):
            session_io.merge_sessions([], '/tmp/out.lpysession')

    # -- validation -----------------------------------------------------------

    def test_import_rejects_bad_format(self):
        session_io = self._get_session_io()
        with tempfile.NamedTemporaryFile('w', suffix='.lpysession', delete=False) as fh:
            json.dump({'format': 'unknown'}, fh)
            fname = fh.name
        try:
            with self.assertRaises(ValueError):
                session_io.import_simulation_from_file(fname, _FakeWidget())
        finally:
            os.unlink(fname)

    # -- helpers --------------------------------------------------------------

    def test_make_relative_paths(self):
        session_io = self._get_session_io()
        paths = ['/a/b/c.py', '/a/b/d.py']
        rel = session_io._make_relative_paths(paths, '/a/b')
        self.assertEqual(rel, ['c.py', 'd.py'])

    def test_make_relative_paths_no_ref(self):
        session_io = self._get_session_io()
        paths = ['/a/b/c.py']
        self.assertEqual(session_io._make_relative_paths(paths, None), ['/a/b/c.py'])


# ---------------------------------------------------------------------------
# CLI tool test
# ---------------------------------------------------------------------------

class TestLpySessionMergeCLI(unittest.TestCase):

    @staticmethod
    def _get_session_io():
        try:
            from openalea.lpy.gui import session_io
            return session_io
        except ImportError:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                'session_io',
                os.path.join(os.path.dirname(__file__), os.pardir, 'src',
                             'openalea', 'lpy', 'gui', 'session_io.py'),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

    def test_cli_help(self):
        import subprocess
        script = os.path.join(
            os.path.dirname(__file__), os.pardir, 'src', 'openalea', 'lpy', 'gui',
            'lpy_session_merge.py',
        )
        result = subprocess.run(
            [sys.executable, script, '--help'],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn('lpy-session-merge', result.stdout)

    def test_cli_merge(self):
        session_io = self._get_session_io()
        s = {
            'format': 'lpysession',
            'version': session_io.SESSION_FORMAT_VERSION,
            'code': '',
            'derivation_length': 1,
            'desc_items': {},
            'scalars': [],
            'panels': [],
            'module_files': [],
            'materials': [],
        }
        with tempfile.NamedTemporaryFile('w', suffix='.lpysession', delete=False) as f1:
            json.dump(s, f1)
            f1_name = f1.name
        with tempfile.NamedTemporaryFile('w', suffix='.lpysession', delete=False) as f2:
            json.dump(s, f2)
            f2_name = f2.name
        out_name = f1_name + '.cli_merged.lpysession'
        try:
            import subprocess
            script = os.path.join(
                os.path.dirname(__file__), os.pardir, 'src', 'openalea', 'lpy', 'gui',
                'lpy_session_merge.py',
            )
            result = subprocess.run(
                [sys.executable, script, f1_name, f2_name, '-o', out_name],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(os.path.exists(out_name))
        finally:
            for n in (f1_name, f2_name, out_name):
                if os.path.exists(n):
                    os.unlink(n)


if __name__ == '__main__':
    unittest.main()
