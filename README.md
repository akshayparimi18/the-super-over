# The Super Over — Step 1 foundation

## Stack
- Frontend: React + TypeScript + Vite
- Backend: Python + FastAPI + native WebSockets
- Rule model: Python enums/dataclasses, with pytest tests

## Prerequisites
- Python 3.11+
- Node.js 20.19+ or 22.12+

## Run the backend (PowerShell)
```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest
fastapi dev app/main.py
```
Backend health: http://127.0.0.1:8000/health
API docs: http://127.0.0.1:8000/docs
WebSocket endpoint: ws://127.0.0.1:8000/ws/DEMO01

## Run the frontend (second terminal, PowerShell)
```powershell
cd frontend
npm install
npm run dev
```
Open the URL Vite prints, usually http://localhost:5173.

## Current scope
Step 1 establishes the frontend shell, API health check, WebSocket connection skeleton, and tested matchup rules. Room creation, player assignment, synchronized rounds, scoring, and reconnection are intentionally left for Step 2 onward.
