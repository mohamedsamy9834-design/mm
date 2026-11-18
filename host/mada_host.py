# Mada Remote Web Host — Windows 7 / Python 3.8 compatible LAN prototype.
# Visible, consent-based only. No stealth or unattended access.
import asyncio
import json
import os
import queue
import secrets
import socket
import threading
import tkinter as tk
from tkinter import messagebox
from pathlib import Path

from aiohttp import web, WSMsgType
import mss
from PIL import Image
import io
import pyautogui

PORT = 8765
MAX_WS_MESSAGE = 1024 * 1024
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01
BASE = Path(__file__).resolve().parent.parent
WEB_DIR = BASE / "web"

def get_lan_ip():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()

class HostApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mada Remote Web — Host")
        self.root.geometry("470x330")
        self.root.resizable(False, False)
        self.root.configure(bg="#10151d")
        self.code = "%06d" % secrets.randbelow(1000000)
        self.pending = queue.Queue()
        self.active_ws = None
        self.server_thread = None
        self.loop = None
        self.runner = None
        self.stop_event = threading.Event()
        self.build_ui()
        self.root.after(150, self.check_approval)
        self.start_server()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        tk.Label(self.root, text="MADA REMOTE WEB", bg="#10151d", fg="white",
                 font=("Segoe UI", 18, "bold")).pack(pady=(22, 5))
        tk.Label(self.root, text="Portable Host • Windows 7", bg="#10151d", fg="#aab7c7",
                 font=("Segoe UI", 10)).pack()
        self.address = tk.Label(self.root, text="Starting local server…", bg="#10151d",
                                fg="#6fc7ff", font=("Segoe UI", 11))
        self.address.pack(pady=(18, 5))
        self.code_label = tk.Label(self.root, text="PAIRING CODE: " + self.code,
                                   bg="#10151d", fg="#65d6a5", font=("Segoe UI", 15, "bold"))
        self.code_label.pack(pady=7)
        self.status = tk.Label(self.root, text="Status: Waiting for a connection",
                               bg="#10151d", fg="#c4ccd7", font=("Segoe UI", 10))
        self.status.pack(pady=10)
        tk.Button(self.root, text="STOP / END REMOTE SESSION", command=self.stop_session,
                  bg="#923c49", fg="white", activebackground="#b24a5a",
                  relief="flat", padx=18, pady=10).pack(pady=8)
        tk.Label(self.root, text="Keep this window visible. Approve every request locally.",
                 bg="#10151d", fg="#9ba9bb", font=("Segoe UI", 9)).pack(pady=6)

    def start_server(self):
        self.server_thread = threading.Thread(target=self.server_worker, daemon=True)
        self.server_thread.start()
        self.address.config(text="Open on same LAN: http://%s:%d" % (get_lan_ip(), PORT))

    def server_worker(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        app = web.Application(client_max_size=MAX_WS_MESSAGE)
        app.router.add_get("/", self.index)
        app.router.add_get("/ws", self.websocket)
        self.runner = web.AppRunner(app)
        self.loop.run_until_complete(self.runner.setup())
        site = web.TCPSite(self.runner, "0.0.0.0", PORT)
        try:
            self.loop.run_until_complete(site.start())
            self.loop.run_forever()
        except Exception as exc:
            self.root.after(0, lambda: self.status.config(text="Server error: " + str(exc)))
        finally:
            if self.runner:
                self.loop.run_until_complete(self.runner.cleanup())
            self.loop.close()

    async def index(self, request):
        path = WEB_DIR / "index.html"
        if not path.exists():
            return web.Response(text="Mada Remote Web UI missing.", status=500)
        return web.FileResponse(str(path))

    async def websocket(self, request):
        code = request.query.get("code", "")
        if not (len(code) == 6 and code.isdigit() and secrets.compare_digest(code, self.code)):
            return web.Response(text="Invalid or expired pairing code.", status=403)

        decision = threading.Event()
        item = {"ip": request.remote or "unknown", "decision": decision, "approved": False}
        self.pending.put(item)

        # Wait for a local user to approve/deny. A timeout avoids stale requests.
        approved = await asyncio.get_event_loop().run_in_executor(None, decision.wait, 60)
        if not approved or not item["approved"] or self.stop_event.is_set():
            return web.Response(text="Request was not approved.", status=403)

        ws = web.WebSocketResponse(heartbeat=20, max_msg_size=MAX_WS_MESSAGE)
        await ws.prepare(request)
        self.active_ws = ws
        self.root.after(0, lambda: self.status.config(
            text="REMOTE SESSION ACTIVE — click Stop to end", fg="#65d6a5"))
        try:
            with mss.mss() as screen:
                monitor = screen.monitors[1]
                screen_w, screen_h = monitor["width"], monitor["height"]
                while not self.stop_event.is_set() and not ws.closed:
                    shot = screen.grab(monitor)
                    frame = Image.frombytes("RGB", shot.size, shot.rgb)
                    frame.thumbnail((1280, 800))
                    buffer = io.BytesIO()
                    frame.save(buffer, format="JPEG", quality=55)
                    await ws.send_bytes(buffer.getvalue())

                    try:
                        msg = await ws.receive(timeout=0.02)
                    except asyncio.TimeoutError:
                        await asyncio.sleep(0.12)
                        continue
                    if msg.type == WSMsgType.TEXT:
                        try:
                            data = json.loads(msg.data)
                            self.handle_input(data, screen_w, screen_h)
                        except Exception:
                            pass
                    elif msg.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
                        break
                    await asyncio.sleep(0.12)
        except Exception:
            pass
        finally:
            self.active_ws = None
            self.root.after(0, lambda: self.status.config(
                text="Status: Waiting for a connection", fg="#c4ccd7"))
        return ws

    def handle_input(self, data, sw, sh):
        action = data.get("action")
        if action in ("move", "click"):
            x = max(0.0, min(1.0, float(data.get("x", 0))))
            y = max(0.0, min(1.0, float(data.get("y", 0))))
            px, py = int(x * sw), int(y * sh)
            if action == "move":
                pyautogui.moveTo(px, py)
            else:
                button = data.get("button", "left")
                if button in ("left", "right"):
                    pyautogui.click(px, py, button=button)
        elif action == "key":
            key = data.get("key", "")
            allowed = set("abcdefghijklmnopqrstuvwxyz0123456789") | {
                "enter", "space", "backspace", "tab", "esc", "up", "down",
                "left", "right", "delete", "home", "end", "pageup", "pagedown",
                "shift", "ctrl", "alt", "f1", "f2", "f3", "f4", "f5", "f6",
                "f7", "f8", "f9", "f10", "f11", "f12"
            }
            if key in allowed:
                pyautogui.press(key)
        elif action == "scroll":
            pyautogui.scroll(max(-5, min(5, int(data.get("amount", 0)))))

    def check_approval(self):
        try:
            while True:
                item = self.pending.get_nowait()
                approved = messagebox.askyesno(
                    "Mada Remote Web — Incoming Request",
                    "A browser at %s wants to view and control this computer.\n\n"
                    "Only approve if you trust the person. Allow this session?" % item["ip"]
                )
                item["approved"] = bool(approved)
                item["decision"].set()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(150, self.check_approval)

    def stop_session(self):
        self.stop_event.set()
        if self.active_ws and self.loop:
            asyncio.run_coroutine_threadsafe(self.active_ws.close(), self.loop)
        self.status.config(text="Session stopped. Restart Host to accept a new request.", fg="#ffb36b")
        self.code = "------"
        self.code_label.config(text="PAIRING CODE: EXPIRED")
        # Stop server loop; restart the app to generate a fresh code.
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)

    def close(self):
        self.stop_session()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    HostApp(root)
    root.mainloop()
