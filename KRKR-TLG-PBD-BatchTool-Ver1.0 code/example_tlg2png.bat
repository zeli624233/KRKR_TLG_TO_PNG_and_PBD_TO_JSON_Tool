@echo off
chcp 65001 >nul
cd /d %~dp0
REM 用法：把下面两个路径改成你自己的目录
python -m krkr_batch_tool tlg2png "D:\input_tlg" -o "D:\output_png" -r -j 8 --overwrite
pause
