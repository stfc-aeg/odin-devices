"""odin_devices package __init__.py."""

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
