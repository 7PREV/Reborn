# Rivals Guard (Light Client Skeleton)

This lightweight client is the desktop companion for Rivals Guard.

## Supported flow
1. Opened from browser via deep-link:
   - `rivalsguard://connect?match_id=<id>&token=<session_token>`
2. Sends connect + heartbeat to backend.
3. Can package evidence files as a ZIP and upload to:
   - `POST /api/guard/alerts/upload`

## Notes
- This skeleton is **Ricochet-safe by design**: no memory writes/read hooks.
- Runs as a background process and only communicates with platform APIs.
- Advanced detections (USB VID/PID, input-pattern, multi-monitor snapshots) should be implemented in signed production modules.

## Run
```bash
pip install -r requirements.txt
python guard_client.py --api http://localhost:8000 --match-id <match_id> --token <session_token>
```

You can also pass protocol URI directly (same behavior as browser deep-link):

```bash
python guard_client.py "rivalsguard://connect?match_id=<id>&token=<session_token>"
```

If the app is opened manually (without match arguments), it now shows an interactive **Arabic GUI**:

- Title: `نظام RivalsGuard للحماية من الغش نشط وجاهز`
- Includes step-by-step instructions for players
- Includes `الانتقال إلى منصة Rivals` button (opens `https://rivalsesports.games/rivalsguard`)
- Supports minimizing to System Tray and manual close (no sudden auto-close)

## Build Windows EXE (hidden console)

Use PyInstaller with `--windowed` so no black CMD window appears to players:

```bash
pyinstaller --clean --noconfirm --onefile --windowed --name RivalsGuard --icon assets/rivalsguard_icon.ico --add-data "assets/rivalsguard_icon.png;assets" guard_client.py
```

Recommended distribution format:

- `RivalsGuard_Setup.zip` (contains `RivalsGuard.exe`)
- The EXE, taskbar, and tray now use the embedded app icon from:
   - `backend/rivals_guard/assets/rivalsguard_icon.ico`
   - `backend/rivals_guard/assets/rivalsguard_icon.png`

## Protocol registration (Windows)
Register `rivalsguard://` URI handler during installer setup and forward `%1` to the EXE.

You can import the template at:

- `backend/rivals_guard/windows/register_rivalsguard_protocol.reg`

After registration, clicking a Rivals deep-link will launch:

`RivalsGuard.exe "rivalsguard://connect?match_id=...&token=..."`
