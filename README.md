# Aura

A chat agent for Vietnamese lunar-calendar and almanac lookups, grounded in
a digitized copy of *Ngọc Hạp Thông Thư*. Ask it about a date in plain
Vietnamese and it resolves the lunar date, Can-Chi, and menh, then looks up
event rules and answers with citations, asking a follow-up
question when it needs more info (birth year, gender, event type).

## Architecture

```
Browser (React SPA)  ──►  FastAPI (app/)  ──►  Gemini (PydanticAI agent)
                                │
                                ▼
                 database/*.json (almanac rules, no DB)
```

Fully stateless: no database, no session store. Conversation history
round-trips through the client as an opaque blob each turn.

## Quickstart

1. Copy `.env.example` to `.env` and fill in `GEMINI_API_KEY`.
2. Run the app:

```bash
docker compose up
```

Or run natively:

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8200
```

Frontend dev server (hot reload, proxies `/api` to `:8200`):

```bash
cd frontend
npm install
npm run dev   # :5273
```

In production the frontend is built (`npm run build` → `frontend/dist`) and
served by FastAPI at `/`, same origin, no CORS — this is what the Dockerfile
does.

## Tests

```bash
uv run pytest
```

## Repo layout

- `app/` — FastAPI service, PydanticAI agent, lunar-calendar and
  almanac-rules lookup modules.
- `frontend/` — React + Vite + TypeScript chat UI.
- `tests/` — pytest suite.
- `database/` — the app's actual data: 4 consolidated JSON files (Can-Chi
  cycle, event rules, bad days, star lookups) extracted from the source
  book. `db/` is the pre-merge, page-tagged precursor of the same data.
- `ocr_all.py` / `ocr_layout.py` — the OCR pipeline (tesseract) that
  produced the raw text `database/`/`db/` were built from. The source PDF
  and OCR scratch output aren't tracked in git (see `.gitignore`) — rerun
  these against `Ngoc Hap Thong Thu.pdf` to regenerate them.
