@echo off
cd /d "%~dp0"
py -3.12 -m pip install -r requirements.txt
if errorlevel 1 (pause & exit /b 1)
py -3.12 -m PyInstaller --clean --noconfirm --onefile --windowed --name SoundMatch --collect-all librosa --collect-all soundfile --collect-all scipy --hidden-import ai_similarity --hidden-import online_discovery app.py
pause
