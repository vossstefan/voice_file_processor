@echo off
echo Installing required packages...
pip install pyinstaller pillow

echo Creating icon...
python create_icon.py

echo Building executable...
python -m PyInstaller voice_buffer_splitter.spec

echo Done! The executable is in the 'dist' folder.
pause 