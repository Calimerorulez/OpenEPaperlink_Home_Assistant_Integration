"""Keep hardware discovery out of unit-test imports.

The renderer suite already stubs these modules; apply that setup consistently
so service and queue tests can also be run independently.
"""
import sys
from unittest.mock import MagicMock

for module in (
    "serial",
    "serial.tools",
    "serial.tools.list_ports",
    "homeassistant.components.bluetooth",
):
    sys.modules.setdefault(module, MagicMock())
