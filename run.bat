@echo off
REM Kiểm tra môi trường ảo đang active
if not exist "venv\Scripts\activate" (
    echo "Chua co venv. Tao moi..."
    python -m venv venv
)

REM Kích hoạt venv
call venv\Scripts\activate

REM Cài các thư viện nếu chưa có
pip install --upgrade pip
pip install -r requirements.txt

REM Chạy app
python app.py

pause