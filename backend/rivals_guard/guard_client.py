import argparse
import json
import os
import sys
import time
import zipfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests


def parse_deep_link(uri: str) -> dict:
    parsed = urlparse(uri)
    if parsed.scheme.lower() != "rivalsguard":
        raise ValueError("Invalid URI scheme")
    q = parse_qs(parsed.query or "")
    return {
        "match_id": (q.get("match_id") or [""])[0],
        "token": (q.get("token") or [""])[0],
    }


def post_json(base_url: str, path: str, payload: dict, jwt: str):
    headers = {"Authorization": f"Bearer {jwt}", "Content-Type": "application/json"}
    r = requests.post(f"{base_url}/api{path}", headers=headers, data=json.dumps(payload), timeout=10)
    r.raise_for_status()
    return r.json()


def connect(base_url: str, jwt: str, match_id: str, token: str, platform: str = "pc"):
    payload = {
        "match_id": match_id,
        "session_token": token,
        "platform": platform,
        "app_version": "guard-client-skeleton-1.0",
        "hwid_hash": "",
    }
    return post_json(base_url, "/guard/session/connect", payload, jwt)


def heartbeat(base_url: str, jwt: str, match_id: str, token: str):
    payload = {"match_id": match_id, "session_token": token}
    return post_json(base_url, "/guard/session/heartbeat", payload, jwt)


def disconnect(base_url: str, jwt: str, match_id: str, token: str):
    payload = {"match_id": match_id, "session_token": token}
    return post_json(base_url, "/guard/session/disconnect", payload, jwt)


def zip_evidence(files: list[str], out_zip: str) -> str:
    out_path = Path(out_zip)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for f in files:
            p = Path(f)
            if p.exists() and p.is_file():
                zf.write(p, arcname=p.name)
    return str(out_path)


def upload_alert(base_url: str, jwt: str, match_id: str, zip_file: str, title: str, description: str):
    headers = {"Authorization": f"Bearer {jwt}"}
    data = {
        "match_id": match_id,
        "title": title,
        "description": description,
        "detection_type": "manual",
        "severity": "high",
        "hwid_hash": "",
    }
    with open(zip_file, "rb") as fh:
        files = {"file": (os.path.basename(zip_file), fh, "application/zip")}
        r = requests.post(f"{base_url}/api/guard/alerts/upload", headers=headers, data=data, files=files, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    parser = argparse.ArgumentParser(description="Rivals Guard client skeleton")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--jwt", default=os.environ.get("RIVALS_JWT", ""))
    parser.add_argument("--deep-link", default="")
    parser.add_argument("--match-id", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--platform", default="pc")
    parser.add_argument("--heartbeat-seconds", type=int, default=20)
    args = parser.parse_args()

    if args.deep_link:
        parsed = parse_deep_link(args.deep_link)
        if not args.match_id:
            args.match_id = parsed["match_id"]
        if not args.token:
            args.token = parsed["token"]

    if not args.jwt or not args.match_id:
        print("Missing --jwt or --match-id")
        sys.exit(2)

    if not args.token:
        args.token = ""

    connect(args.api.rstrip("/"), args.jwt, args.match_id, args.token, args.platform)
    print("[Guard] connected")

    try:
        while True:
            heartbeat(args.api.rstrip("/"), args.jwt, args.match_id, args.token)
            time.sleep(max(8, args.heartbeat_seconds))
    except KeyboardInterrupt:
        pass
    finally:
        try:
            disconnect(args.api.rstrip("/"), args.jwt, args.match_id, args.token)
        except Exception:
            pass
        print("[Guard] disconnected")


if __name__ == "__main__":
    main()
