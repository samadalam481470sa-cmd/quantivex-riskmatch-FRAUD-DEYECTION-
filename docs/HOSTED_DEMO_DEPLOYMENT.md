# Recruiter-ready deployment guide

## What the hosted application is

The Vercel build exposes a **public, read-only synthetic demonstration**.
The responsive interface calls the actual Python/FastAPI backend for a
small, fixed catalog of synthetic case studies. Its behavioral and temporal
graph risk calculations are real code from this repository, not static numbers.

The demo shows: legitimate payment, anomalous amount/device/country,
circular money-flow ring, and rapid account layering. It reconstructs the
prior transactions, returns explainable findings, and shows the simulated
decision. **All records and explanations are synthetic.**

## What the hosted application is not

This is **not a production banking backend**. The `app.py` deployment entrypoint
unconditionally sets `RISK_MESH_PUBLIC_DEMO=true` before importing the API,
so all credential-protected transaction, batch, ML, verification and
investigation endpoints return 404. It does not connect to or persist
customer payments. The protected local/container application is deliberately
not deployed on Vercel because its SQLite store cannot provide durable
transaction records or high availability on an ephemeral serverless platform.

## Deploy from Git

1. Connect this GitHub repo to a new Vercel project with the **FastAPI** preset.
2. Set the project root to the repository root, Python dependencies from
   `requirements.txt`, and production branch to `main`.
3. Leave financial API secrets **unset**. Do not enable or configure
   `RISK_MESH_ENV=production` on the public showcase.
4. Deploy, then verify `GET /`, `GET /health`,
   `GET /api/v1/demo/cases`,
   `GET /api/v1/demo/investigate/circular-ring`,
   `GET /assets/dashboard.css` and `GET /assets/dashboard.js`.
5. Confirm unauthenticated `POST /api/v1/score` is 404 in the deployed
   public mode, and the browser shows a live **BLOCK** demonstration for
   circular ring without any actual payment enforcement.

If deployment protection is enabled, Vercel may require you to authorize
viewer access or adjust protection settings in your own project.
Do not disable authentication on a deployment that contains real data.

## Local reviewer experience

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
uvicorn riskmesh.api:app --port 8000
```

Open `http://localhost:8000/` and click *Run investigation*.
The local project is for development and uses synthetic data by default.

## Production blockers

A live multi-tenant financial backend still needs a proper persistent
database and migrations, deployed identity-provider trust, encrypted
storage and backups, KMS key lifecycle, tested recovery procedures,
external penetration testing, operational alerting, and independent
fraud-model evaluation on representative authorized labeled data.
See `docs/OPERATIONS_RUNBOOK.md` and `docs/MODEL_VALIDATION.md`.
