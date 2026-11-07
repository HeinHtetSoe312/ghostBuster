@echo off
cd /d "%~dp0"
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q -r requirements.txt
if not exist models\ghost_predictor.joblib python train_model.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
