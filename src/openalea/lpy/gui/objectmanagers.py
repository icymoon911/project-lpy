from glob import glob
from os.path import join, dirname, basename, splitext
import threading
import warnings
import sys
import traceback

try:
    import py2exe_release
except ImportError:
    py2exe_release = False


def __get_plugins_path():
    p = dirname(__file__)
    return join(p, 'plugins')


def __read_manager_plugins():
    managers = []
    if not py2exe_release:
        pluginpath = __get_plugins_path()
        # Mutate sys.path only inside a try/finally so it is always restored,
        # even if a plugin import raises.
        sys.path.insert(0, pluginpath)
        try:
            pattern = join(pluginpath, '*.py')
            listplugins = glob(pattern)
            listplugins = [splitext(basename(i))[0] for i in listplugins]
            listplugins = [i for i in listplugins if i[:2] != '__']
        finally:
            # Restore sys.path immediately, regardless of what happened above.
            try:
                sys.path.remove(pluginpath)
            except ValueError:
                pass

        for plugin in listplugins:
            _import_plugin_managers(plugin, managers, py2exe=False)
    else:
        from .plugins import curve2dmanager as cm
        from .plugins import functionmanager as fm
        from .plugins import nurbspatchmanager as nm
        for plugin in (cm, fm, nm):
            _import_plugin_managers(plugin, managers, py2exe=True)

    return managers


def _import_plugin_managers(plugin, managers, py2exe):
    """Import *plugin* and append its managers to the *managers* list."""
    try:
        if not py2exe:
            mod = __import__(plugin)
        else:
            mod = plugin
    except ImportError as e:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
        warnings.warn("Cannot import " + str(plugin) + " : " + str(e))
        return

    try:
        lmanagers = getattr(mod, 'get_managers')()
        try:
            iter(lmanagers)
            managers += lmanagers
        except TypeError:
            managers.append(lmanagers)
    except Exception as e:
        exc_info = sys.exc_info()
        traceback.print_exception(*exc_info)
        warnings.warn("Cannot import " + str(plugin) + " : " + str(e))


# ---------------------------------------------------------------------------
# Thread-safe singleton cache
# ---------------------------------------------------------------------------
#
# The manager list is built once (on first call) and then cached.  We use a
# ``threading.Lock`` so concurrent first-calls from multiple threads don't
# both try to import plugins simultaneously.
# ---------------------------------------------------------------------------

__MANAGERS = None
__MANAGERS_LOCK = threading.Lock()


def get_managers():
    """Return the cached manager dict, building it on first access.

    Thread-safe: uses a module-level ``threading.Lock``.
    """
    global __MANAGERS
    if __MANAGERS is not None:
        return __MANAGERS
    with __MANAGERS_LOCK:
        # Double-checked locking – another thread may have populated the
        # cache while we were waiting for the lock.
        if __MANAGERS is None:
            managers = __read_manager_plugins()
            __MANAGERS = {m.typename: m for m in managers}
    return __MANAGERS
