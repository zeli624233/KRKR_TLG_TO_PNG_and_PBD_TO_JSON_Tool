@echo off
chcp 65001 >nul
cd /d %~dp0
REM 用法：把下面路径改成你自己的目录。第一次使用前可先运行 config-plugin 或在 GUI 里选择 plugin 文件夹
python -m krkr_batch_tool json2pbd "D:\input_json" -o "D:\output_pbd" -r -j 4 --overwrite
pause
