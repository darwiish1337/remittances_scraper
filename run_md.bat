@echo off
cd /d "%~dp0"
title M-D Intelligence Engine
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cls
".\venv\Scripts\python.exe" main.py
pause
