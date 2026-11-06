@echo off
cd /d "%~dp0"
py -3.12 -m pip install -r requirements-ai-build.txt
if errorlevel 1 (pause & exit /b 1)
py -3.12 -m PyInstaller --clean --noconfirm --onedir --windowed --name SoundMatchAI --collect-all torch --collect-all transformers --collect-all tokenizers --collect-all safetensors --collect-all librosa --collect-all soundfile --collect-all scipy --collect-all numba --hidden-import ai_similarity --hidden-import online_discovery --hidden-import online_audio --hidden-import online_audio_ui app.py
pause
