# Discovery notes

Fill after running dump_molekule_devices.py:

| Friendly | API subProduct.name | Observed mode values | Filter keys | sensordata keys |
|----------|---------------------|----------------------|-------------|-----------------|
| Mini Plus | | | | |
| Mini Plus 2 | | | | |
| Original | | | | |

Provisional original preset mapping (confirm/replace from dump):
- silent → record observed `mode` / action path from dump
- auto → likely `smart` / `enable-smart-mode` (confirm)
- boost → likely `burst` field or max fanspeed action (confirm)
