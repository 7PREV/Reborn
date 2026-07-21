import argparse
import ctypes
import json
import os
import sys
import threading
import time
import webbrowser
import zipfile
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import requests


RIVALS_GUARD_PAGE = "https://rivalsesports.games/rivalsguard"


def _show_info_card(message: str, title: str = "RivalsGuard") -> None:
    try:
        import tkinter as tk

        root = tk.Tk()
        root.title(title)
        root.configure(bg="#0B0D11")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        width, height = 560, 190
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = max(0, int((screen_w - width) / 2))
        y = max(0, int((screen_h - height) / 2))
        root.geometry(f"{width}x{height}+{x}+{y}")

        frame = tk.Frame(root, bg="#0B0D11", highlightthickness=1, highlightbackground="#1F2937")
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        title_lbl = tk.Label(
            frame,
            text="🛡️ نظام الحماية RivalsGuard",
            fg="#F8FAFC",
            bg="#0B0D11",
            font=("Segoe UI", 14, "bold"),
            anchor="e",
            justify="right",
        )
        title_lbl.pack(fill="x", padx=16, pady=(14, 6))

        body_lbl = tk.Label(
            frame,
            text=message,
            fg="#D1D5DB",
            bg="#0B0D11",
            font=("Segoe UI", 10),
            wraplength=500,
            justify="right",
            anchor="e",
        )
        body_lbl.pack(fill="x", padx=16, pady=(0, 14))

        ok_btn = tk.Button(
            frame,
            text="إغلاق",
            command=root.destroy,
            bg="#10B981",
            fg="#07110D",
            activebackground="#34D399",
            activeforeground="#07110D",
            relief="flat",
            padx=16,
            pady=5,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        ok_btn.pack(anchor="e", padx=16, pady=(0, 14))

        root.mainloop()
    except Exception:
        try:
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        except Exception:
            pass


def _open_platform_page() -> None:
    try:
        webbrowser.open(RIVALS_GUARD_PAGE)
    except Exception:
        pass


def _show_manual_launcher_window() -> None:
    try:
        import tkinter as tk
        from PIL import Image, ImageDraw
        import pystray

        root = tk.Tk()
        root.title("نظام الحماية RivalsGuard")
        root.configure(bg="#0B0D11")
        root.resizable(False, False)
        root.attributes("-topmost", True)

        width, height = 700, 420
        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        x = max(0, int((screen_w - width) / 2))
        y = max(0, int((screen_h - height) / 2))
        root.geometry(f"{width}x{height}+{x}+{y}")

        tray_state: dict[str, object] = {"icon": None}

        def _stop_tray_icon() -> None:
            icon = tray_state.get("icon")
            if not icon:
                return
            try:
                icon.stop()
            except Exception:
                pass
            tray_state["icon"] = None

        def _close_app() -> None:
            _stop_tray_icon()
            root.destroy()

        def _restore_from_tray(icon=None, item=None) -> None:
            _stop_tray_icon()
            root.after(0, lambda: (root.deiconify(), root.lift(), root.focus_force()))

        def _open_from_tray(icon=None, item=None) -> None:
            _open_platform_page()

        def _close_from_tray(icon=None, item=None) -> None:
            root.after(0, _close_app)

        tray_minimizing = {"active": False}

        def _minimize_to_tray() -> None:
            try:
                tray_minimizing["active"] = True
                if tray_state.get("icon"):
                    root.withdraw()
                    return

                icon_image = Image.new("RGBA", (64, 64), (11, 13, 17, 255))
                draw = ImageDraw.Draw(icon_image)
                draw.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(16, 185, 129, 255))
                draw.text((19, 18), "RG", fill=(7, 17, 13, 255))

                menu = pystray.Menu(
                    pystray.MenuItem("فتح النافذة", _restore_from_tray),
                    pystray.MenuItem("الانتقال إلى منصة Rivals", _open_from_tray),
                    pystray.MenuItem("إغلاق", _close_from_tray),
                )
                icon = pystray.Icon("RivalsGuard", icon_image, "RivalsGuard", menu)
                tray_state["icon"] = icon

                root.withdraw()
                threading.Thread(target=icon.run, daemon=True).start()
            except Exception:
                root.iconify()
            finally:
                tray_minimizing["active"] = False

        root.protocol("WM_DELETE_WINDOW", _minimize_to_tray)

        def _on_unmap(_event=None):
            try:
                if tray_minimizing["active"]:
                    return
                if root.state() == "iconic":
                    _minimize_to_tray()
            except Exception:
                pass

        root.bind("<Unmap>", _on_unmap)

        frame = tk.Frame(root, bg="#0B0D11", highlightthickness=1, highlightbackground="#1F2937")
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        title_lbl = tk.Label(
            frame,
            text="نظام الحماية RivalsGuard",
            fg="#F8FAFC",
            bg="#0B0D11",
            font=("Segoe UI", 18, "bold"),
            anchor="e",
            justify="right",
        )
        title_lbl.pack(fill="x", padx=20, pady=(20, 8))

        subtitle = tk.Label(
            frame,
            text="نظام RivalsGuard نشط وجاهز. يرجى بدء المباريات مباشرة من منصة Rivals.",
            fg="#9CA3AF",
            bg="#0B0D11",
            font=("Segoe UI", 11),
            anchor="e",
            justify="right",
        )
        subtitle.pack(fill="x", padx=20, pady=(0, 10))

        steps_text = (
            "1️⃣ افتح منصة Rivals في متصفحك.\n"
            "2️⃣ انضم إلى مباراتك أو بطولتك مع كلانك.\n"
            "3️⃣ اضغط زر \"بدء المباراة\" في الموقع، وسيتم تفعيل الحماية وتوجيهك أوتوماتيكياً."
        )
        steps_lbl = tk.Label(
            frame,
            text=steps_text,
            fg="#E5E7EB",
            bg="#0B0D11",
            font=("Segoe UI", 11),
            justify="right",
            anchor="e",
            wraplength=620,
        )
        steps_lbl.pack(fill="x", padx=20, pady=(0, 16))

        button_row = tk.Frame(frame, bg="#0B0D11")
        button_row.pack(fill="x", padx=20, pady=(0, 18))

        open_btn = tk.Button(
            button_row,
            text="الانتقال إلى منصة Rivals",
            command=_open_platform_page,
            bg="#10B981",
            fg="#07110D",
            activebackground="#34D399",
            activeforeground="#07110D",
            relief="flat",
            padx=14,
            pady=7,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2",
        )
        open_btn.pack(side="right")

        tray_btn = tk.Button(
            button_row,
            text="تصغير إلى شريط النظام",
            command=_minimize_to_tray,
            bg="#1F2937",
            fg="#E5E7EB",
            activebackground="#374151",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=7,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        tray_btn.pack(side="right", padx=(0, 8))

        close_btn = tk.Button(
            button_row,
            text="إخفاء إلى الخلفية",
            command=_minimize_to_tray,
            bg="#111827",
            fg="#D1D5DB",
            activebackground="#1F2937",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=12,
            pady=7,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        )
        close_btn.pack(side="left")

        root.mainloop()
    except Exception:
        _show_info_card(
            "نظام الحماية RivalsGuard نشط وجاهز — يرجى بدء المباريات من منصة Rivals مباشرة.",
            title="RivalsGuard",
        )


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
    parser.add_argument("protocol_uri", nargs="?", default="")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--jwt", default=os.environ.get("RIVALS_JWT", ""))
    parser.add_argument("--deep-link", default="")
    parser.add_argument("--match-id", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--platform", default="pc")
    parser.add_argument("--heartbeat-seconds", type=int, default=20)
    args = parser.parse_args()

    raw_protocol_uri = (args.protocol_uri or "").strip()
    if raw_protocol_uri.lower().startswith("rivalsguard://") and not args.deep_link:
        args.deep_link = raw_protocol_uri

    launched_without_context = (not args.deep_link) and (not args.match_id) and (not args.jwt)
    if launched_without_context:
        _show_manual_launcher_window()
        return

    if args.deep_link:
        parsed = parse_deep_link(args.deep_link)
        if not args.match_id:
            args.match_id = parsed["match_id"]
        if not args.token:
            args.token = parsed["token"]

    if not args.jwt or not args.match_id:
        _show_info_card(
            "تعذر بدء جلسة الحماية: معلومات المباراة غير مكتملة. يرجى تشغيل المباراة من منصة Rivals.",
            title="RivalsGuard",
        )
        sys.exit(2)

    if not args.token:
        args.token = ""

    connect(args.api.rstrip("/"), args.jwt, args.match_id, args.token, args.platform)

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


if __name__ == "__main__":
    main()
