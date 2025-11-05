# This file makes the tools directory a Python package.

# Import extended tools to register them automatically
try:
    from selfai.tools import extended_tools  # noqa: F401
except ImportError:
    pass  # Extended tools are optional