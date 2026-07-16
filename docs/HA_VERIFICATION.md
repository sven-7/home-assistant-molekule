# HA verification checklist (Task 8)

Install this branch via HACS custom repository `sven-7/home-assistant-molekule` (branch `feature/mini-original-support` or merge to `main` first), restart Home Assistant, reload the Molekule integration.

## Checklist

- [ ] Mini Plus (Lounge): Auto Protect preset works
- [ ] Mini Plus (Lil boy): Auto Protect preset works
- [ ] Minis: fan speeds 1–5
- [ ] Original (Biggy): Silent / Auto / Boost presets work (provisional — compare to Molekule app)
- [ ] Original: PECO + Pre-filter sensors present with sensible values
- [ ] Minis: AQI + PECO; PM2.5 if available
- [ ] Existing config entry still loads (domain `molekule` unchanged)
- [ ] Logs: no unexpected "Unknown Molekule model" spam

## If Original presets mismatch the app

1. In the Molekule app, set Biggy to Silent, dump, then Auto, dump, then Boost, dump:

```bash
cd /Users/stephen/src/home-assistant-molekule/.worktrees/mini-original-support
source .venv/bin/activate
MOLEKULE_EMAIL='...' MOLEKULE_PASSWORD='...' python scripts/dump_molekule_devices.py
```

2. Compare `mode` / `silent` / `burst` / `fanspeed` and update `fan_helpers.original_preset_*` accordingly.
