@echo off
chcp 65001 >nul
cd /d %~dp0
python -m pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --onedir --windowed --name KRKR_TLG_PBD_Tool ^
  --add-data "pbd_converter_assets;pbd_converter_assets" ^
  start_gui.py
pyinstaller --noconfirm --onedir --console --name KRKR_TLG_PBD_CLI ^
  --add-data "pbd_converter_assets;pbd_converter_assets" ^
  start_cli.py
pause
