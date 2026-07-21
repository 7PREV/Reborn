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

## Protocol registration (Windows)
Register `rivalsguard://` URI handler during installer setup and forward arguments to `guard_client.py`.
