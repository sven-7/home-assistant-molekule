import sys
from pathlib import Path
from types import ModuleType

# Stub homeassistant so const.py imports without the full HA package.
ha = ModuleType("homeassistant")
ha_const = ModuleType("homeassistant.const")
ha_const.CONF_EMAIL = "email"
ha_const.CONF_PASSWORD = "password"
sys.modules.setdefault("homeassistant", ha)
sys.modules.setdefault("homeassistant.const", ha_const)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "custom_components" / "molekule"))
