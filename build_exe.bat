@echo off
setlocal
title Kabutopz Voice Protocol v7.1 - EXE Builder

echo ==============================================
echo   KABUTOPZ VOICE PROTOCOL v7.1
echo   Clean folder release - no self-extracting overlay
echo ==============================================
echo.

python --version
if errorlevel 1 (
    echo ERROR: Python was not found.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
if errorlevel 1 goto :error

python -m pip install -r requirements.txt
if errorlevel 1 goto :error

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist KabutopzVoiceProtocol.spec del /q KabutopzVoiceProtocol.spec

python -m PyInstaller --noconfirm --clean --onedir --noupx --contents-directory "_internal" --name KabutopzVoiceProtocol --windowed --version-file "version_info.txt" --icon "assets\kabutopz_app_icon.ico" --add-data "assets\kabutopz_app_icon.png;assets" --add-data "assets\kabutopz_header_full.png;assets" --add-data "assets\kabutopz_love.png;assets" --add-data "assets\kabutopz_watermark.jpg;assets" --add-data "assets\buy_me_a_coffee.png;assets" starcitizen_voice_keybinds.py
if errorlevel 1 goto :error

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
