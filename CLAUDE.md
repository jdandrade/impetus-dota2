# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Impetus is an open-source Dota 2 performance analytics platform. It calculates IMP (Individual Match Performance) scores using a Ridge Regression model trained on 6,236 Stratz match samples with per-position coefficients (positions 1-5). The platform includes a web frontend, a scoring microservice, and a Discord bot.

## Monorepo Structure

Three services in a pnpm workspace (`pnpm-workspace.yaml` includes `apps/*`, `services/*`, `packages/*`):

```
impetus-dota2/
├── apps/web/                          # Next.js 14 frontend (App Router)
├── services/imp-engine/               # Python FastAPI scoring microservice
├── services/professor-impetus/        # Discord bot (match tracking, AI roasts)
├── data/                              # ML coefficients (penta_role_coefficients.py)
├── scripts/                           # Training & data scripts (solve_formula.py)
└── PLAN.md                            # Architecture plan & API contract
```

## Development Commands

| Task | Command |
|------|---------|
| Install all deps | `pnpm install` |
| Run web client | `cd apps/web && pnpm dev` |
| Run IMP Engine | `cd services/imp-engine && uvicorn app.main:app --reload --port 8000` |
| Run Discord bot | `cd services/professor-impetus && python app/main.py` |
| Run engine tests | `cd services/imp-engine && pytest` |
| Lint web app | `cd apps/web && pnpm lint` |
| Build web app | `cd apps/web && pnpm build` |
| Python syntax check | `cd services/professor-impetus && python -m py_compile app/main.py` |

## Pre-Commit Checks

1. **Web changes:** `cd apps/web && pnpm lint` — catches unused imports, TS errors, ESLint violations
2. **Discord bot changes:** `cd services/professor-impetus && python -m py_compile app/main.py`
3. **Significant web changes:** `cd apps/web && pnpm build`

Watch for: unused imports when removing JSX elements, missing imports when adding components.

## Architecture

### Data Flow

```
OpenDota/Stratz API → Web Client → IMP Engine → Score Response
                         ↓
              Gemini AI (coach analysis)
```

The Discord bot (`professor-impetus`) independently polls OpenDota/Stratz for tracked players' matches, sends stats to IMP Engine, and generates AI roast summaries via Gemini.

### IMP Scoring Engine (`services/imp-engine/`)

- **Tech:** Python 3.11, FastAPI, Pydantic v2
- **Version:** `0.6.0-penta-role` (set in `app/core/scoring.py` as `ENGINE_VERSION`)
- **Endpoint:** `POST /api/v1/calculate-imp` (response model: `CalculateIMPResponse`)
- **Health:** `GET /health` and `GET /` (root)
- **Algorithm:** Ridge Regression with per-position coefficients (20+ features each)
- **Formula:** `IMP = Intercept + Σ(stat × coefficient) + WinLossBonus` (win: +12, loss: -8)
- **Score range:** -65 to +65 (clamped)
- **Grade thresholds (raw score):** S (≥40), A (≥20), B (≥5), C (≥-5), D (≥-20), F (<-20)
- **Coefficients:** Inline in `app/core/scoring.py` (also exported in `data/penta_role_coefficients.py`)
- **Role mapping:** carry→1, mid→2, offlane→3, support→4, hard_support→5
- **Key files:**
  - `app/main.py` — FastAPI app with CORS middleware
  - `app/core/scoring.py` — All scoring logic, coefficients, grade thresholds
  - `app/models/request.py` — `CalculateIMPRequest` (Pydantic model with validation)
  - `app/models/response.py` — `CalculateIMPResponse`, `IMPData`, `ContributingFactor`
- **Dependencies:** `fastapi`, `uvicorn`, `pandas`, `scipy`, `numpy`, `pydantic`
- **Docker:** Python 3.11-slim, copies from repo root (`services/imp-engine/`)
- **Railway:** Dockerfile builder, healthcheck at `/health`

### Web App (`apps/web/`)

- **Tech:** Next.js 14.2 (App Router), React 18, TypeScript (strict), Tailwind CSS 3.4
- **Path alias:** `@/*` → `./src/*` (tsconfig paths)
- **ESLint:** extends `next/core-web-vitals` and `next/typescript`
- **Key dependencies:** `framer-motion` (animations), `recharts` (charts), `lucide-react` (icons), `react-markdown`, `clsx`, `tailwind-merge`
- **Pages (all `"use client"`):**
  - `/` — Home page with match search, "Nerd of the Day", recent matches, tracked players
  - `/match/[id]` — Match analysis: fetches from OpenDota, calculates IMP for all 10 players, shows scoreboard, lane matchups, net worth graph, AI coach analysis
  - `/player/[id]` — Player profile with recent matches, win/loss, peers (accepts Steam64 ID)
- **Data layer:**
  - `src/lib/providers/` — Provider abstraction: `DotaDataProvider` interface with `OpenDotaProvider` (primary) + `StratzProvider` (fallback on 429), composed in `FallbackDataProvider`
  - `src/lib/opendota.ts` — Direct OpenDota API client (used by match page), hero data, role detection, benchmarks
  - `src/lib/providers/stratz.ts` — Stratz GraphQL API fallback (requires `NEXT_PUBLIC_STRATZ_API_TOKEN`)
  - `src/lib/imp-client.ts` — IMP Engine client, TypeScript interfaces mirroring Python models
  - `src/lib/transformer.ts` — Transforms OpenDota data → IMP Engine request format; role detection by net worth ranking within team
  - `src/lib/gemini.ts` — Gemini 2.5 Flash API client for AI coaching analysis (supports "drunk mode")
  - `src/lib/items.ts` — Item ID → name/image mappings
  - `src/lib/abilities.ts` — Ability ID → name mappings
  - `src/lib/lane-analysis.ts` — Lane matchup calculation from gold_t data
  - `src/lib/tracked-players.ts` — Hardcoded Steam64/Steam32 → name mappings for "tracked" players who get AI coaching
  - `src/lib/match-cache.ts` — localStorage cache for enriched match data (100 matches per player limit)
  - `src/hooks/useMatchHistory.ts` — localStorage-backed recent match history (5 max)
- **Components:**
  - `src/components/match/Scoreboard.tsx` — Full Radiant/Dire scoreboard with IMP scores, items, MVP crown
  - `src/components/match/CoachAnalysis.tsx` — AI coaching analysis via Gemini (only for tracked players)
  - `src/components/match/NetWorthGraph.tsx` — Gold advantage over time (Recharts)
  - `src/components/match/LaneMatchups.tsx` — Lane matchup outcomes visualization
  - `src/components/match/RoleIcon.tsx` — Position/role icon component
- **Theme:** Dark mode only (`<html class="dark">`), cyber aesthetic
  - Primary purple: `#A855F7` / Secondary teal: `#14B8A6`
  - Surface colors: `cyber-bg` (#0A0A0F), `cyber-surface` (#12121A), `cyber-surface-light` (#1A1A25)
  - Glassmorphism via `glass` CSS class
  - Glow shadows: `shadow-glow` (purple), `shadow-glow-teal`
  - Fonts: Geist Sans + Geist Mono (local fonts loaded in layout.tsx)
- **Images:** Remote patterns configured for `cdn.cloudflare.steamstatic.com`, `cdn.dota2.com`, `www.opendota.com`
- **Deployment:** Vercel (`vercel.json` with npm build/install)

### Discord Bot (`services/professor-impetus/`)

- **Tech:** Python 3.11, discord.py ≥2.3, aiohttp, pydantic-settings
- **Entry:** `app/main.py` — Initializes bot, match tracker, YouTube tracker, nerd tracker
- **Core modules:**
  - `app/bot.py` — `ProfessorBot` (discord.Client subclass), embed builders, match/video/nerd announcements
  - `app/tracker.py` — `MatchTracker`: polls OpenDota for tracked players' new matches, calculates IMP scores, generates Gemini roasts
  - `app/youtube_tracker.py` — `YouTubeTracker`: daily Dota 2 educational video posts at configurable hour (default 21:00 GMT), AI-triaged via Gemini
  - `app/nerd_tracker.py` — `NerdOfTheDayTracker`: daily "most addicted" player post at 00:00 Portuguese time
  - `app/config.py` — `Settings` (pydantic-settings from env), `TRACKED_PLAYERS` dict, Steam ID conversion, adaptive poll interval (10min normal, 30min off-hours 2-8am Portugal)
- **Services:**
  - `app/services/opendota.py` — OpenDota API client (async, aiohttp)
  - `app/services/providers/stratz.py` — Stratz fallback provider
  - `app/services/imp_engine.py` — IMP Engine HTTP client
  - `app/services/gemini.py` — Gemini AI client for roast generation
  - `app/services/youtube.py` — YouTube Data API v3 client
  - `app/services/redis_store.py` — Redis state management (tracking which matches have been announced)
  - `app/services/email_notifier.py` — SMTP email notifications for errors
- **Prompts:** `app/prompts/` — Gemini prompt templates for roasts and video triage
- **Tracked players:** 6 players defined in `app/config.py` (Steam64 IDs)
- **Dependencies:** `discord.py`, `aiohttp`, `redis`, `google-generativeai`, `google-api-python-client`, `pydantic`, `pydantic-settings`, `python-dotenv`, `pytz`
- **Docker:** Python 3.11-slim, runs `python -m app.main`
- **Railway:** Dockerfile builder, restart on failure (max 5 retries)

## Key Patterns and Conventions

### Role Detection
Roles are determined by net worth ranking within a team (highest NW = Carry/Pos1, lowest = Hard Support/Pos5). This is implemented in both:
- `apps/web/src/lib/transformer.ts` (`detectRoleByNetWorth`)
- `apps/web/src/lib/opendota.ts` (`detectRole`)

### Provider Fallback Pattern
Both the web app and Discord bot implement OpenDota → Stratz fallback when OpenDota returns HTTP 429 (rate limited). The web app uses a `FallbackDataProvider` class in `src/lib/providers/fallback.ts`.

### Steam ID Conversion
Steam64 → Steam32 (account ID): subtract `76561197960265728`. Used in both web (`steam64ToSteam32`) and bot (`convert_steam_id64_to_account_id`).

### Tracked Players
A set of hardcoded players receive special features:
- **Web:** AI coaching analysis via Gemini on match pages (`src/lib/tracked-players.ts`)
- **Bot:** Match polling, roast announcements, Nerd of the Day (`app/config.py`)

When adding a new tracked player, update both `apps/web/src/lib/tracked-players.ts` (Steam64 + Steam32 maps) and `services/professor-impetus/app/config.py` (TRACKED_PLAYERS dict).

## Environment Variables

**Web** (`apps/web/.env.local`):
- `NEXT_PUBLIC_IMP_ENGINE_URL` — IMP Engine URL (default: `http://localhost:8000`)
- `NEXT_PUBLIC_GEMINI_API_KEY` — Gemini API key for AI coaching
- `NEXT_PUBLIC_STRATZ_API_TOKEN` — Stratz API token for fallback

**IMP Engine** (`services/imp-engine/.env`):
- `PORT` — Server port (default: `8000`)
- `ALLOWED_ORIGINS` — CORS origins, comma-separated or `*`

**Discord Bot** (`services/professor-impetus/.env`):
- `DISCORD_TOKEN` — Discord bot token (required)
- `DISCORD_CHANNEL_ID` — Target channel ID
- `GEMINI_API_KEY` — Gemini API key (required)
- `REDIS_URL` — Redis connection URL
- `IMP_ENGINE_URL` — IMP Engine URL
- `FRONTEND_URL` — Frontend URL for "View Match" buttons
- `POLL_INTERVAL_SECONDS` — Normal hours poll interval (default: 600)
- `OFF_HOURS_POLL_INTERVAL` — Off-hours poll interval (default: 1800)
- `STRATZ_API_TOKEN` — Stratz API fallback token
- `YOUTUBE_API_KEY` — YouTube Data API v3 key (optional)
- `YOUTUBE_POST_HOUR_GMT` — Hour to post daily video (default: 21)
- `SMTP_SERVER`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` — Email notifications (optional)

## Deployment

- **Frontend:** Vercel (auto-deploys, `vercel.json` config)
- **IMP Engine:** Railway.app (Docker, healthcheck at `/health`)
- **Discord Bot:** Railway.app (Docker, restart on failure)
- **Production URLs:**
  - Frontend: `https://impetus-dota2.vercel.app`
  - IMP Engine: `https://impetus-dota2-production.up.railway.app`

## Scripts & Data

- `scripts/solve_formula.py` — Trains Ridge Regression model on Stratz samples, outputs coefficients
- `scripts/fetch_stratz_truth.py` — Fetches ground truth IMP scores from Stratz API
- `scripts/announce_v020.py` — Version announcement script
- `data/penta_role_coefficients.py` — Exported coefficients (also inline in `app/core/scoring.py`)
