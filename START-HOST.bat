@echo off
cd /d %~dp0
py -3.8 -m pip install -r requirements-win7.txt
py -3.8 host\mada_host.py
pause
