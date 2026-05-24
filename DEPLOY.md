# Deploy Cricket Intelligence

Deploy the **backend** on [Render](https://render.com) and the **frontend** on [Vercel](https://vercel.com).

## Prerequisites

- GitHub repo with this project pushed
- [Groq API key](https://console.groq.com/keys)
- `backend/cricket.db` committed (~28 MB) — required for the API to answer queries

---

## 1. Deploy backend (Render)

### Option A — Blueprint (`render.yaml`)

1. Push the repo to GitHub.
2. In Render: **New → Blueprint** → connect the repo.
3. Render reads `render.yaml` at the repo root.
4. Set **GROQ_API_KEY** when prompted (secret).
5. Set **ALLOWED_ORIGINS** after you know your Vercel URL (see step 2), e.g.  
   `https://cricket-intelligence.vercel.app`  
   For multiple origins, comma-separate:  
   `http://localhost:5173,https://cricket-intelligence.vercel.app`
6. Deploy. Note the service URL, e.g. `https://cricket-intelligence-api.onrender.com`.

### Option B — Manual Web Service

1. **New → Web Service** → connect GitHub repo.
2. Settings:

   | Field | Value |
   |--------|--------|
   | **Root Directory** | `backend` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | **Health Check Path** | `/health` |

3. **Environment variables**

   | Key | Value |
   |-----|--------|
   | `GROQ_API_KEY` | your Groq key |
   | `ALLOWED_ORIGINS` | your Vercel URL (and `http://localhost:5173` if you test locally against prod API) |

4. **Create Web Service** and wait for deploy.

### Verify backend

```bash
curl https://YOUR-SERVICE.onrender.com/health
# {"status":"ok"}

curl -X POST https://YOUR-SERVICE.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Who scored the most runs in IPL?"}'
```

**Note:** Free Render services spin down after inactivity; the first request may take 30–60 seconds.

---

## 2. Deploy frontend (Vercel)

1. **Add New Project** → import the same GitHub repo.
2. **Root Directory:** `frontend` (important).
3. **Framework Preset:** Vite (auto-detected).
4. **Build Command:** `npm run build`
5. **Output Directory:** `dist`
6. **Environment variables** (Production):

   | Key | Value |
   |-----|--------|
   | `VITE_API_URL` | `https://YOUR-SERVICE.onrender.com` (no trailing slash) |

7. Deploy.

### Verify frontend

Open the Vercel URL, ask a question, and confirm the network tab calls `https://YOUR-SERVICE.onrender.com/ask`.

---

## 3. Link CORS (after Vercel deploy)

1. Copy your Vercel URL, e.g. `https://cricket-intelligence-xyz.vercel.app`.
2. In Render → your service → **Environment** → edit **ALLOWED_ORIGINS**:
   ```
   https://cricket-intelligence-xyz.vercel.app,http://localhost:5173
   ```
3. Save (Render redeploys automatically).

Custom domains: add those URLs to `ALLOWED_ORIGINS` as well.

---

## Local development

**Backend**

```bash
cd backend
cp .env.example .env   # add GROQ_API_KEY
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend**

```bash
cd frontend
cp .env.example .env   # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

---

## Checklist

- [ ] Repo pushed to GitHub with `backend/cricket.db`
- [ ] Render service live; `/health` returns `ok`
- [ ] `GROQ_API_KEY` set on Render
- [ ] Vercel project root = `frontend`
- [ ] `VITE_API_URL` set on Vercel to Render URL
- [ ] `ALLOWED_ORIGINS` on Render includes Vercel URL
- [ ] End-to-end test from production frontend

---

## Troubleshooting

| Issue | Fix |
|--------|-----|
| CORS error in browser | Add exact Vercel URL (scheme + host, no path) to `ALLOWED_ORIGINS` on Render |
| API calls `localhost` in prod | Set `VITE_API_URL` on Vercel and redeploy |
| 502 / timeout on first request | Render free tier cold start; retry after ~1 min |
| `GROQ_API_KEY` errors | Check key in Render env; no quotes around value |
| 404 on Vercel refresh | `vercel.json` rewrites are included for SPA routing |
