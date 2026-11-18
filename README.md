# Mada Remote Web — Portable Windows 7 starter

A consent-based remote desktop prototype. The controlled Windows PC runs a small portable Host agent; the controller uses a browser.

## Included
- `host/mada_host.py`: visible Host agent with Tkinter status window.
- `web/index.html`: browser-based Controller UI.
- `requirements-win7.txt`: pinned Python dependencies.
- `START-HOST.bat`: starts the Host agent.
- `README.md`: setup and safety notes.

## Compatibility target
Windows 7 SP1, Python 3.8.10 (the final Python release line supporting Windows 7). Use matching 32-bit or 64-bit Python for your OS. This is source-portable; it is not yet a compiled standalone EXE.

## Setup
1. On the controlled PC, install Python 3.8.10.
2. Extract this folder anywhere, including a USB drive.
3. Double-click `START-HOST.bat`.
4. The Host window displays its LAN address and a temporary 6-digit code.
5. On another PC on the same trusted private LAN, open a modern browser and visit the shown address, for example `http://192.168.1.20:8765`.
6. Enter the temporary code. The Host user must approve the request in the visible confirmation dialog.
7. Close the browser session or click Stop in the Host window to end access.

## Build a portable folder
Install dependencies and run `py -3.8 host\mada_host.py`. To bundle later, use PyInstaller on a Windows 7 build machine:
`py -3.8 -m pip install pyinstaller==5.13.2`
`py -3.8 -m PyInstaller --noconfirm --clean --onedir --windowed --name MadaHost host\mada_host.py`
Copy `web`, `requirements-win7.txt`, and the generated `dist\MadaHost` folder together, then adjust the web directory path if packaging it into a single folder.

## Network and security limitations
- This starter works only on a trusted private LAN.
- It uses plain HTTP/WebSocket and does not encrypt traffic. Do not use it on public Wi-Fi, do not expose it to the Internet, and do not configure router port forwarding.
- Do not use it for unattended access. Every connection requires local approval; the Host window shows an active-session indicator and Stop button.
- For access over the Internet, a production version needs TLS/WSS, authenticated signaling, a secure relay, rate limits, session expiry, and security review. Those are not implemented here.
- The browser controller should be a current browser. Windows 7 itself is not recommended for Internet-facing use.
