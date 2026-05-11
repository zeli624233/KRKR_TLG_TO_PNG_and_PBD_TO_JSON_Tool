@echo off
chcp 65001 >nul
cd /d %~dp0
REM 用法：把下面路径改成你自己的目录。plugin 目录里需要 json.dll 和 PackinOne.dll
python -m krkr_batch_tool pbd2json "D:\input_pbd" -o "D:\output_json" -r -j 4 --plugin-dir "D:\game\plugin"
pause
