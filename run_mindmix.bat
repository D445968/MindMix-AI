@echo off
cd /d C:\Users\swdc2\vscode\mindmix

REM 如果 env 資料夾存在，啟動虛擬環境
if exist env\Scripts\activate (
    call env\Scripts\activate
)

REM 如果沒有虛擬環境，就直接用系統的 Python 啟動
python -m streamlit run app.py

pause
