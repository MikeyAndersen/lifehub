@echo off
rem One-click manual drain: skip the GPU-idle check and empty the queue now.
cd /d "%~dp0"
python gpu_agent.py --now %*
pause
