# Fortexa — Deployment Guide

## Architecture

```
Browser
  │
  ├── Frontend (React/Vite static) ──→ Vercel (free, CDN)
  └── API calls (/api/*) ──────────→ Backend (FastAPI + PyTorch) ──→ Render (Docker)
```

---

## Step 1: Push code to GitHub

```bash
cd "Final year project/deepfake"
git init && git add . && git commit -m "Fortexa launch"
git remote add origin https://github.com/<username>/fortexa.git
git push -u origin main
```

> `.gitignore` me `node_modules`, `data/source_faces`, `data/demo_dataset`,
> `backend/fortexa.db` add karna (model `runs/model.pth` push karo — 43MB, zaroori hai).

## Step 2: Deploy backend on Render (free)

1. https://dashboard.render.com → **New +** → **Blueprint**
2. Repo select karo — `render.yaml` auto-detect hoga
3. Env var set karo jab puche:
   - `FRONTEND_ORIGIN` = abhi `https://placeholder.vercel.app` daal do (baad me update)
4. Deploy ~5-8 min (torch install hota hai)
5. Milega URL jaise: `https://fortexa-backend.onrender.com`
6. Test: `https://fortexa-backend.onrender.com/api/health` → `"status": "ok"`

## Step 3: Deploy frontend on Vercel (free)

1. https://vercel.com → **Add New Project** → repo import karo
2. Settings:
   - **Root Directory**: `deepfake/frontend` (ya jahan frontend hai)
   - **Environment variable**:
     - `VITE_API_URL` = `https://fortexa-backend.onrender.com/api`
3. Deploy → milega `https://fortexa-xxx.vercel.app`

## Step 4: CORS fix (zaroori!)

Render dashboard → fortexa-backend → Environment:
- `FRONTEND_ORIGIN` = `https://fortexa-xxx.vercel.app`
- Save → auto redeploy

Done. Ab live website ready.

---

## Local Docker (optional — Docker Desktop install karke)

```bash
cd deepfake
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/docs

---

## Important notes

| Cheez | Detail |
|-------|--------|
| Cold start | Free Render 15 min idle ke baad sleep — pehli request ~50s leti hai |
| Persistence | Free tier pe DB/uploads redeploy pe reset. Paid ($7/mo) me `render.yaml` me disk uncomment karo |
| Model | `runs/model.pth` image ke andar baked hai — alag se upload nahi karna |
| Video scans | Free tier RAM 512MB — lambi videos fail ho sakti hain, chhoti test video use karo |
