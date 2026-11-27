@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" quality_studio_desktop.py
) else (
  py -3 quality_studio_desktop.py
)
if errorlevel 1 (
  echo VPP launcher failed. Install Python with Tk and VPP dependencies first.
  pause
)
