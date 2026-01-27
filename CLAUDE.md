# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Impetus is an open-source Dota 2 performance analytics platform. It calculates IMP (Individual Match Performance) scores using a Ridge Regression model trained on 6,236 Stratz match samples with role-specific coefficients (positions 1-5).

## Monorepo Structure

Three services in a pnpm workspace:

- **`apps/web/`** — Next.js 14 (App Router) frontend with TypeScript, Tailwind CSS, Framer Motion, Recharts
- **`services/imp-engine/`** — Python FastAPI microservice that calculates IMP scores
- **`services/professor-impetus/`** — Discord bot that tracks pro players, posts match roasts (Gemini AI), and daily YouTube educational videos

## Development Commands

| Task | Command |
|------|---------|
| Install all deps | `pnpm install` |
| Run web client | `cd apps/web && pnpm dev` |
| Run IMP Engine | `cd services/imp-engine && uvicorn app.main:app --reload --port 8000` |
| Run Discord bot | `cd services/professor-impetus && python app/main.py` |
| Run both (Docker) | `docker-compose up` |
| Run engine tests | `cd services/imp-engine && pytest` |
| Lint web app | `cd apps/web && pnpm lint` |
| Python syntax check | `cd services/professor-impetus && python -m py_compile app/main.py` |
| Build web app | `cd apps/web && pnpm build` |

## Pre-Commit Checks

1. **Web changes:** `cd apps/web && pnpm lint` — catches unused imports, TS errors, ESLint violations
2. **Discord bot changes:** `cd services/professor-impetus && python -m py_compile app/main.py`
3. **Significant web changes:** `cd apps/web && pnpm build`

Watch for: unused imports when removing JSX elements, missing imports when adding components.

## Architecture

### Data Flow

```
OpenDota/Stratz API → Web Client → API Proxy Route → IMP Engine → Score Response
                                                         ↑
                                          Ridge Regression (penta-role coefficients)
```

The Discord bot (`professor-impetus`) independently polls OpenDota for tracked players' matches, sends stats to IMP Engine, and generates AI roast summaries via Gemini.

### IMP Scoring Engine (v0.6.0-penta-role)

- **Endpoint:** `POST /api/v1/calculate-imp`
- **Algorithm:** Ridge Regression with per-position coefficients (20+ features each)
- **Formula:** `IMP = Intercept + Σ(stat × coefficient) + WinLossBonus` (win: +12, loss: -8)
- **Score range:** -65 to +65
- **Grade scale:** S (90-100), A (75-89), B (60-74), C (45-59), D (30-44), F (0-29)
- **Coefficients source:** `data/penta_role_coefficients.py` (trained via `scripts/solve_formula.py`)

### Web App (Next.js)

- App Router with route groups: `(dashboard)/match/[id]`, `(dashboard)/player/[id]`
- Path alias: `@/*` → `src/`
- Data providers in `src/lib/providers/`: OpenDota (primary) + Stratz (fallback for rate limiting)
- API proxy at `src/app/api/imp/route.ts` forwards to IMP Engine
- Theme: dark mode, cyber aesthetic (purple `#A855F7`, teal `#14B8A6`), glassmorphism

### Discord Bot (Professor Impetus)

- Tracks 7+ pro players, polls for new matches at configurable intervals
- Generates roast summaries with Gemini AI (includes hero name puns for losses)
- YouTube tracker: daily educational Dota 2 video posts, AI-triaged via Gemini
- Uses Redis for state management

## Environment Variables

**Web** (`apps/web/`): `NEXT_PUBLIC_IMP_ENGINE_URL`

**IMP Engine** (`services/imp-engine/`): `PORT`, `ALLOWED_ORIGINS`

**Discord Bot** (`services/professor-impetus/`): `DISCORD_TOKEN`, `DISCORD_CHANNEL_ID`, `GEMINI_API_KEY`, `REDIS_URL`, `IMP_ENGINE_URL`, `POLL_INTERVAL_SECONDS`, `YOUTUBE_API_KEY` (optional), `YOUTUBE_POST_HOUR_GMT`

See `.env.example` files in each service directory.

## Deployment

- **Frontend:** Vercel
- **Backend services:** Railway.app (Docker-based, see `railway.json` in each service)
- **Production URLs:** `https://impetus.vercel.app`, `https://impetus-dota2-production.up.railway.app`
