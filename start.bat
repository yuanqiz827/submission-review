@echo off
chcp 65001 >nul
cd /d "%~dp0"
python -c "import flask, psycopg" >nul 2>&1
if errorlevel 1 (
    echo 請先安裝 Python，並在此資料夾執行：python -m pip install -r requirements.txt
    pause
    exit /b 1
)
echo 網站啟動後，請在瀏覽器開啟 http://localhost:5000
echo 請保持此視窗開啟；按 Ctrl+C 停止網站。
python app.py
if errorlevel 1 pause
