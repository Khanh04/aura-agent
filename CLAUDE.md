# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Aura: a chat agent for Vietnamese lunar-calendar/almanac lookups, grounded
in a digitized copy of *Ngọc Hạp Thông Thư* (`database/*.json`, `Ngoc Hap
Thong Thu.pdf` at repo root). A user converses naturally ("ngày 15/8/2026
cưới có tốt không, tôi sinh năm 1995?"); a PydanticAI agent (Gemini
flash-lite) resolves the lunar date, calls tools to pull the relevant raw
almanac rules, and synthesizes an answer with citations — asking a
follow-up question when it's missing something a rule needs (date, event
type, birth year, gender), instead of guessing.

`database/` is a *rule engine*, not a calendar — it has no Gregorian↔lunar
conversion table for real years (`luc_thap_hoa_giap` is the abstract 60-year
Can-Chi cycle; everything else keys off lunar month/day/Can-Chi, not
Gregorian dates). Date conversion is a separate, vendored algorithm (see
below). `db/` (48 page-tagged files) is the pre-merge source of the 4
`database/*.json` files — the app only reads `database/`, `db/` is unused.

## Commands

```bash
uv sync                                      # install/update deps
uv run uvicorn app.main:app --reload --port 8200   # dev server on :8200
uv run pytest                                # run tests
uv run pytest tests/test_almanac_rules.py::test_kim_lau_matches_book_examples  # single test
docker compose up                            # containerized app
```

Frontend (from `frontend/`):
```bash
npm run dev      # Vite dev server on :5273, proxies /api -> localhost:8200
npm run build    # tsc -b && vite build -> frontend/dist, served by FastAPI in prod/Docker
```

There is no lint command configured (no ruff/eslint config present).

## Architecture

### Request flow
```
Browser (React SPA, served by FastAPI at "/")
  │ POST /api/v1/chat  { message, history }
  ▼
FastAPI (app/main.py)
  │ prepends "(Hôm nay là <today>.)" to the prompt
  │ deserializes history via pydantic-ai's ModelMessagesTypeAdapter
  ▼
PydanticAI Agent (app/agent/aura_agent.py, google:gemini-flash-lite-latest)
  │ tool calls -> app/services/lunar_calendar.py (date math, pure functions)
  │            -> app/services/almanac_rules.py (JSON lookups, pure functions)
  ▼
ChatReply { message, lunar } -> ChatResponse { reply, lunar, history }
```

**No server-side session store.** The full conversation is round-tripped
through the client as an opaque JSON blob (`result.all_messages()` via
`to_jsonable_python`) each turn — the frontend never inspects or constructs
it, just stores and replays it. This keeps the backend fully stateless; no
DB, no session cookies. If chat history needs to survive a page reload,
that's a `localStorage` one-liner in the frontend, not a backend change.

### Date conversion (`app/services/lunar_calendar.py`)
The core JDN/new-moon/sun-longitude math is adapted from the `vnlunar` PyPI
package (MIT, based on Ho Ngoc Duc's algorithm), **vendored, not a runtime
dependency** — it's a small, stable algorithm and `vnlunar` is an
unmaintained single-author "beta" package. `time_zone` is fixed at 7.0
(modern Vietnam/UTC+7); Vietnam used UTC+8 before 1967, so pre-1967 dates
can occasionally get the wrong leap-month placement near month boundaries —
accepted, not fixed, since the app's supported range is ~1900-2100.

Day/month Can-Chi use hardcoded universal Can/Chi name arrays (true
constants of the calendar system). **Year** Can-Chi/menh/nạp-âm is instead
resolved by indexing into `core_astrology.json`'s `luc_thap_hoa_giap` table
(`(year - 4) % 60`, `divmod` into the 30 two-year-pair entries) rather than
a second hardcoded name list, so the app's wording always matches the
source book.

### Almanac rules (`app/services/almanac_rules.py`)
Plain functions, JSON loaded once via `functools.lru_cache` — no
repository/query-builder layer, mirroring argus-agent's `db.py` convention
(plain functions over data, here JSON instead of sqlite3.Row).

`get_event_rules(event_type)` deliberately returns the **whole** raw
category block (cuoi_hoi/lam_nha/an_tang/xuat_hanh) instead of filtering by
month/day — `events_rules.json`'s sub-rules use inconsistent field names
across ~45-60 differently-shaped entries per category (some keyed by
`thang`, some by `mua`/season, some by `tuoi`/age, some by nothing). A
generic filter would silently drop rules that don't match its assumptions,
which is worse than returning too much; the agent (which has the resolved
lunar date/Can-Chi in conversation context) picks out what's relevant and
cites `source_page`.

Three functions are **person-specific**, not just date-specific — the agent
must ask for birth year (and, for burial, gender) before calling them:
- `get_kim_lau(birth_year, target_lunar_year)` — bad-luck age check for
  cưới hỏi/làm nhà. Uses **last-digit-of-age mod 10** in `{1,3,6,8}`, not
  the mod-9 the book's own prose note claims — the book's own worked
  examples (`vi_du_tuoi_pham: [21,23,26,28]`) only satisfy mod 10 (e.g.
  `23 % 9 == 5`, not in the set, but `23 % 10 == 3` is). Trusted the
  concrete examples over the apparently-mistranscribed prose.
- `get_cuc_thong_thien_khieu(birth_can_chi, age)` — 18-cục cycle (làm
  nhà/cưới hỏi), 10 years per cục starting from the birth Can-Chi's cục,
  wrapping after 18. Follows the block's explicit `cach_tinh` prose; its own
  worked example (`vi_du`) is garbled OCR and actually contradicts that same
  prose (shows 3 different cục across 3 consecutive ages within one decade,
  impossible under a 10-year-per-cục rule) — the file elsewhere admits OCR
  quality issues nearby, so the clearly-stated rule was trusted over the
  unreadable example.
- `get_trung_tang(birth_year, death_lunar_year, gender)` — burial-only; the
  12-cung counting direction genuinely differs by the deceased's gender
  (`nam` starts at cung Dần counting backward, `nữ` at cung Thân counting
  forward — both explicit in the source data, not an assumption).

### Agent (`app/agent/aura_agent.py`)
Single PydanticAI `Agent` ("Aura", `google:gemini-flash-lite-latest`,
structured output `ChatReply`). No `AgentDeps`/`deps_type` — every tool is
a pure function of its arguments, so all tools use `@aura_agent.tool_plain`
(no `RunContext` boilerplate). `convert_date` is a real tool (not computed
once per-request in the route, since the date comes from free-form
conversation, not a form field) — the agent resolves relative expressions
("hôm nay", "tuần sau") itself using the real current date the route
prepends to the prompt, then calls `convert_date` with an unambiguous ISO
date; the agent never computes lunar math itself.

Instructions (in Vietnamese, matching the app's all-Vietnamese domain)
cover: tool-grounded answers only (no generic trained-in lore), mapping
free-text event descriptions to the closest of the 4 curated categories
with an explicit "this is an approximation" disclosure, asking exactly one
follow-up question when person-specific data is missing, surfacing the
book's internal rule conflicts (`luu_y` notes) instead of picking a side,
citing `source_page`, and plain-text output (no Markdown — the chat bubbles
render text verbatim, not through a Markdown renderer).

### Config (`app/config.py`)
Single `pydantic-settings` `Settings` object with one field:
`GEMINI_API_KEY` (see `.env.example`). No DB path, no worker/callback
secrets — no multi-service trust boundary in this app at all.

### Frontend (`frontend/src/`)
Plain React state (`ChatWindow.tsx`, no state library) — `messages` for
display and a separate opaque `history` blob round-tripped to the backend
unchanged. `LunarResult.tsx` renders the structured lunar-date card inline
under an assistant bubble when a reply includes one. Hand-rolled CSS driven
by `tokens.css` custom properties (warm lacquer-red/gold palette), no UI
framework.

## Known ceilings (deliberate, not bugs)

- Lunar conversion assumes modern UTC+7 Vietnam; pre-1967 dates can be off
  near leap-month boundaries (see `lunar_calendar.py` module docstring).
- No auth, no rate limiting, no multi-user.
- No persistence of chat history server-side or across page reloads
  (client-memory only; the opaque `history` blob is lost on refresh).
- No caching of repeated `/api/v1/chat` LLM calls.
- No streaming responses.
- `get_cuc_thong_thien_khieu`'s age-to-cục stepping formula is the best
  available reading of a book section with an internally-contradictory
  worked example (OCR damage) — see `almanac_rules.py`'s docstring there.
