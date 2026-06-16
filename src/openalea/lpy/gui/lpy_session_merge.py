"""
Command-line tool to merge several ``.lpysession`` files into one.

Usage::

    lpy-session-merge session1.lpysession session2.lpysession ... -o merged.lpysession

The first input file provides the code, derivation length, description items
and scalars.  Object panels from every input file are appended in order.
"""

import argparse
import os
import sys


def _import_merge():
    """Import ``merge_sessions`` from the installed package or the local tree."""
    try:
        from openalea.lpy.gui.session_io import merge_sessions
        return merge_sessions
    except ImportError:
        pass
    # Fallback: import session_io directly relative to this script
    here = os.path.dirname(os.path.abspath(__file__))
    spec_path = os.path.join(here, 'session_io.py')
    import importlib.util
    spec = importlib.util.spec_from_file_location('session_io', spec_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.merge_sessions


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='lpy-session-merge',
        description='Merge several .lpysession files into a single file.',
    )
    parser.add_argument(
        'inputs',
        nargs='+',
        metavar='INPUT',
        help='Input .lpysession file(s) to merge.',
    )
    parser.add_argument(
        '-o', '--output',
        required=True,
        metavar='OUTPUT',
        help='Output .lpysession file path.',
    )

    args = parser.parse_args(argv)

    merge_sessions = _import_merge()

    try:
        merge_sessions(args.inputs, args.output)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1

    print(f'Merged {len(args.inputs)} session(s) into {args.output!r}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
