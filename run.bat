@echo off
chcp 65001 >nul

echo ================================
echo      ASSETONE - AUTO RUN
echo ================================

REM Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Khong tim thay Python. Vui long cai Python truoc.
    pause
    exit /b 1
)

REM Tao venv neu chua co
if not exist "venv\Scripts\activate.bat" (
    echo Chua co venv. Dang tao moi...
    python -m venv venv
)

REM Kich hoat venv
call venv\Scripts\activate.bat

REM Nang cap pip
echo Dang nang cap pip...
python -m pip install --upgrade pip

REM Tao requirements.txt neu chua co
if not exist "requirements.txt" (
    echo Chua co requirements.txt. Dang tao file mac dinh...
    (
        echo flask
        echo flask-cors
        echo pymongo
        echo python-dotenv
        echo requests
        echo openpyxl
    ) > requirements.txt
)

REM Cai thu vien
echo Dang cai thu vien tu requirements.txt...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo Cai thu vien that bai. Vui long kiem tra requirements.txt.
    pause
    exit /b 1
)

REM Kiem tra thu vien
echo Dang kiem tra thu vien...
python -m pip check

if errorlevel 1 (
    echo Thu vien dang bi loi phu thuoc.
    pause
    exit /b 1
)

REM Chay app
echo Dang chay app.py...
python app.py

pause