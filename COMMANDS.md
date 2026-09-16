# VisualAI — Project Execution Commands & Step-by-Step Guide

This document contains all the commands needed to run, test, and manage the VisualAI project on Windows.

---

## 🚀 Quick Start (Easiest Way)

Simply double-click `start.bat` in the project root, or in PowerShell run:

```powershell
.\start.bat
```

This script automatically verifies Docker / Qdrant and starts the FastAPI server.

---

## 📋 Step-by-Step Manual Execution

### Step 1: Start Docker / Qdrant Vector Database

1. Open **Docker Desktop** on your computer.
2. Check if the `qdrant` container is running or start it:

```powershell
# Start the existing container
docker start qdrant
```

*(If creating for the very first time or recreating)*:
```powershell
docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage:z qdrant/qdrant
```

> **Note:** Even if Docker is closed, the project automatically falls back to embedded on-disk storage (`storage/qdrant/`). Docker is only required if you want the visual web dashboard.

---

### Step 2: Open Project Directory

Open PowerShell or Command Prompt:

```powershell
cd "d:\ai video generation\AI-VIDEO-GENERATOR"
```

---

### Step 3: Verify Dependencies (One-time or after updates)

```powershell
pip install -r requirements.txt
```

---

### Step 4: Run the VisualAI Server

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, you will see:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Application startup complete.
```

---

## 🌐 Application Links

| Resource | URL | Description |
|---|---|---|
| **API Documentation (Swagger UI)** | [http://localhost:8000/docs](http://localhost:8000/docs) | Test file uploads interactively in the browser |
| **API Documentation (ReDoc)** | [http://localhost:8000/redoc](http://localhost:8000/redoc) | Clean readable API reference |
| **Health Check** | [http://localhost:8000/health](http://localhost:8000/health) | Verifies server status |
| **Qdrant Vector Dashboard** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Inspect collections & Layer A stored vectors |

---

## 🧪 How to Test Ingesting a File

### Option A: Using the Browser (Swagger UI)
1. Open [http://localhost:8000/docs](http://localhost:8000/docs)
2. Expand the `POST /upload` endpoint.
3. Click **Try it out**.
4. Choose any supported study file (`.pdf`, `.png`, `.jpg`, `.txt`, `.mp4`, `.mov`, `.mkv`).
5. Click **Execute** to run extraction, structuring, and Layer A RAG sync.

### Option B: Using PowerShell / curl

```powershell
curl.exe -X POST "http://localhost:8000/upload" -F "file=@your_lecture_or_notes.pdf"
```

---

## 🛑 How to Stop the Services

### Stop FastAPI Server:
In the terminal where uvicorn is running, press:
```
Ctrl + C
```

### Stop Docker Container:
```powershell
docker stop qdrant
```

---

## 🔧 Useful Maintenance Commands

| Action | Command |
|---|---|
| Check running Docker containers | `docker ps` |
| View Qdrant logs | `docker logs -f qdrant` |
| Restart Qdrant | `docker restart qdrant` |
| Check if port 8000 is occupied | `Get-NetTCPConnection -LocalPort 8000` |
| Check if port 6333 is occupied | `Get-NetTCPConnection -LocalPort 6333` |
