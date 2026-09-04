@echo off
setlocal
title Kabutopz Voice Protocol v1.0 - EXE Builder
cd /d "%~dp0"

set "BUILD_PYTHON=build\.venv\Scripts\python.exe"

echo ==============================================
echo   KABUTOPZ VOICE PROTOCOL v1.0
echo   Clean folder release - no self-extracting overlay
echo ==============================================
echo.

python --version
if errorlevel 1 (
    echo ERROR: Python was not found.
    pause
    exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist KabutopzVoiceProtocol.spec del /q KabutopzVoiceProtocol.spec

echo Creating a clean build environment...
python -m venv "build\.venv"
if errorlevel 1 goto :error

"%BUILD_PYTHON%" -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto :error

"%BUILD_PYTHON%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :error

"%BUILD_PYTHON%" -m PyInstaller --noconfirm --clean --onedir --noupx --contents-directory "_internal" --name KabutopzVoiceProtocol --windowed --version-file "version_info.txt" --icon "assets\kabutopz_app_icon.ico" --exclude-module torch --exclude-module whisper --exclude-module faster_whisper --exclude-module ctranslate2 --exclude-module onnxruntime --exclude-module tensorflow --exclude-module pocketsphinx --exclude-module vosk --add-data "assets\kabutopz_app_icon.png;assets" --add-data "assets\kabutopz_header_full.png;assets" --add-data "assets\kabutopz_love.png;assets" --add-data "assets\kabutopz_watermark.jpg;assets" --add-data "assets\buy_me_a_coffee.png;assets" starcitizen_voice_keybinds.py
if errorlevel 1 goto :error

rem SpeechRecognition ships offline data and FLAC tools for other systems.
rem This app uses Google recognition and needs only the Windows FLAC tool.
if exist "dist\KabutopzVoiceProtocol\_internal\speech_recognition\pocketsphinx-data" rmdir /s /q "dist\KabutopzVoiceProtocol\_internal\speech_recognition\pocketsphinx-data"
if exist "dist\KabutopzVoiceProtocol\_internal\speech_recognition\flac-linux-x86" del /q "dist\KabutopzVoiceProtocol\_internal\speech_recognition\flac-linux-x86"
if exist "dist\KabutopzVoiceProtocol\_internal\speech_recognition\flac-linux-x86_64" del /q "dist\KabutopzVoiceProtocol\_internal\speech_recognition\flac-linux-x86_64"
if exist "dist\KabutopzVoiceProtocol\_internal\speech_recognition\flac-mac" del /q "dist\KabutopzVoiceProtocol\_internal\speech_recognition\flac-mac"

certutil -hashfile "dist\KabutopzVoiceProtocol\KabutopzVoiceProtocol.exe" SHA256 > "dist\KabutopzVoiceProtocol\SHA256.txt"

echo.
echo BUILD COMPLETE
echo Keep the entire folder together:
echo %CD%\dist\KabutopzVoiceProtocol
echo.
echo EXE:
echo %CD%\dist\KabutopzVoiceProtocol\KabutopzVoiceProtocol.exe
pause
exit /b 0

:error
echo.
echo BUILD FAILED
pause
exit /b 1
