# NetraCare frontend

Minimalist-light React + TypeScript app for the NetraCare AI front desk.
Built per `../FRONTEND_BLUEPRINT.md` (layout/behavior contracts preserved,
skin swapped). The backend is the authority for identity, data, and rules.

## Run

```bash
# terminal 1 — backend
cd ../backend && source .venv/bin/activate && uvicorn app.main:app --reload

# terminal 2 — frontend
npm install
npm run dev        # http://localhost:5173, /api/* proxied to :8000
```

Production build against a deployed API:

```bash
VITE_API_BASE_URL=https://api.example.com npm run build
```

No live LLM or Weaviate keys are needed for development: chat answers and
retrieval work out of the box, and `NETRACARE_STUB_SAFETY=1` on the backend
bypasses the red-flag LLM call for rule testing.

## Checks

```bash
npm run lint     # tsc --noEmit
npm run build    # typecheck + production bundle
```
