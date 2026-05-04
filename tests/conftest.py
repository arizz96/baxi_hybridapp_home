"""
Pytest configuration for testing without HA instance.

Mocks homeassistant module so the API can be tested in isolation.
This is the standard approach used by Home Assistant custom component developers.
"""

import sys
from unittest.mock import MagicMock

# Mock homeassistant before importing the custom component
# Use nested dictionaries to create a mock that supports any attribute access
ha_mock = MagicMock()
ha_mock.__getitem__ = MagicMock(return_value=MagicMock())
ha_mock.__setitem__ = MagicMock()

sys.modules['homeassistant'] = ha_mock
sys.modules['homeassistant.core'] = MagicMock()
sys.modules['homeassistant.config_entries'] = MagicMock()
sys.modules['homeassistant.const'] = MagicMock()
sys.modules['homeassistant.util'] = MagicMock()
sys.modules['homeassistant.util.dt'] = MagicMock()
sys.modules['homeassistant.helpers'] = MagicMock()
sys.modules['homeassistant.helpers.entity'] = MagicMock()
sys.modules['homeassistant.helpers.entity_platform'] = MagicMock()
sys.modules['homeassistant.helpers.update_coordinator'] = MagicMock()
sys.modules['homeassistant.components'] = MagicMock()
sys.modules['homeassistant.components.sensor'] = MagicMock()
sys.modules['homeassistant.logging'] = MagicMock()

# Mock requests library
sys.modules['requests'] = MagicMock()
