# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Impetus is an open-source Dota 2 performance analytics platform. It calculates IMP (Individual Match Performance) scores using a Ridge Regression model trained on 6,236 Stratz match samples with per-position coefficients (positions 1-5). The platform includes a web frontend, a scoring microservice, and a Discord bot.

## Monorepo Structure

A pnpm workspace (`pnpm-workspace.yaml` includes `apps/*`, `services/*`, `packages/*`):

```
impetus-dota2/
├── apps/web/                          # Next.js 14 frontend (App Router)
├── packages/group-lore/               # Shared Python package: player identities & group lore
├── services/imp-engine/               # Python FastAPI scoring microservice
├── services/professor-impetus/        # Discord bot — Dota 2 match tracking, AI roasts
├── services/wow-tracker/              # Discord bot — WoW Mythic+ run tracking, AI roasts
├── services/aoe2-tracker/             # Discord bot — AoE2 match tracking, AI roasts
├── data/                              # ML coefficients (penta_role_coefficients.py)
└── scripts/                           # Training & data scripts (solve_formula.py)
```

## Development Commands

| Task | Command |
|------|---------|
| Install all deps | `pnpm install` |
| Run web client | `cd apps/web && pnpm dev` |
| Run IMP Engine | `cd services/imp-engine && uvicorn app.main:app --reload --port 8000` |
| Run Dota 2 Discord bot | `cd services/professor-impetus && python app/main.py` |
| Run WoW Discord bot | `cd services/wow-tracker && python -m app.main` |
| Run engine tests | `cd services/imp-engine && pytest` |
| Lint web app | `cd apps/web && pnpm lint` |
| Build web app | `cd apps/web && pnpm build` |
| Syntax check (professor-impetus) | `cd services/professor-impetus && python -m py_compile app/main.py` |
| Syntax check (wow-tracker) | `cd services/wow-tracker && python -m py_compile app/main.py` |
| Run AoE2 Discord bot | `cd services/aoe2-tracker && python -m app.main` |
| Syntax check (aoe2-tracker) | `cd services/aoe2-tracker && python -m py_compile app/main.py` |

## Pre-Commit Checks

1. **Web changes:** `cd apps/web && pnpm lint` — catches unused imports, TS errors, ESLint violations
2. **Dota 2 bot changes:** `cd services/professor-impetus && python -m py_compile app/main.py`
3. **WoW bot changes:** `cd services/wow-tracker && python -m py_compile app/main.py`
4. **AoE2 bot changes:** `cd services/aoe2-tracker && python -m py_compile app/main.py`
5. **Significant web changes:** `cd apps/web && pnpm build`

Watch for: unused imports when removing JSX elements, missing imports when adding components.

## Architecture

### Data Flow

```
OpenDota/Stratz API → Web Client → IMP Engine → Score Response
                         ↓
              Gemini AI (coach analysis)
```

The Dota 2 Discord bot (`professor-impetus`) independently polls OpenDota/Stratz for tracked players' matches, sends stats to IMP Engine, and generates AI roast summaries via Gemini. The WoW Discord bot (`wow-tracker`) polls Raider.IO for tracked characters' Mythic+ runs and generates AI roast announcements via Gemini. All three bots share player identity data from the `group-lore` package.

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

### Shared Player Lore (`packages/group-lore/`)

- **Tech:** Python 3.11, dataclasses, setuptools
- **Purpose:** Centralizes player identities, personality archetypes, aliases, and roast instructions shared across all Discord bots
- **Key files:**
  - `group_lore/players.py` — `Player` dataclass, `PLAYERS` dict (8 players), `resolve_player(name)` (case-insensitive alias substring match), `build_players_prompt_block()`, `build_name_mappings()`
  - `group_lore/discord_lore.py` — `DISCORD_LORE` for non-player Discord members
  - `group_lore/__init__.py` — Re-exports all public symbols
- **Install:** `pip install packages/group-lore/` (installed in Dockerfiles of consuming services)
- **Used by:** `professor-impetus`, `wow-tracker`, `aoe2-tracker`

### Dota 2 Discord Bot (`services/professor-impetus/`)

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
- **Docker:** Python 3.11-slim, installs `group-lore` from repo root, runs `python -m app.main`
- **Railway:** Dockerfile builder, restart on failure (max 5 retries)

### WoW Mythic+ Tracker (`services/wow-tracker/`)

- **Tech:** Python 3.11, discord.py ≥2.3, aiohttp, pydantic-settings
- **Entry:** `app/main.py` — Initializes bot, Redis, Gemini, Raider.IO client, starts tracker
- **Core modules:**
  - `app/tracker.py` — `MythicPlusTracker`: polls Raider.IO for tracked characters' new M+ runs, detects group runs (multiple tracked players in same run), deduplicates announcements
  - `app/bot.py` — `build_run_embed()` (Discord embed builder), `RunView` (Discord UI with Raider.IO link)
  - `app/config.py` — `Settings` (pydantic-settings from env), `TRACKED_CHARACTERS` dict (7 WoW characters across 6 players), adaptive poll interval (10min normal, 30min off-hours 2-8am Portugal)
- **Services:**
  - `app/services/raiderio.py` — Raider.IO API client (async, aiohttp, rate-limited), `CURRENT_SEASON` constant (must be updated each WoW season)
  - `app/services/gemini.py` — Gemini AI client for M+ roast generation
  - `app/services/redis_store.py` — Redis state management (per-character last run ID, per-run announcement dedup)
- **Prompts:** `app/prompts/mythicplus_roast.py` — WoW-specific system/user prompts using `group-lore`
- **Tracked characters:** 7 characters defined in `app/config.py` (Raider.IO name/realm/region)
- **Dependencies:** `discord.py`, `aiohttp`, `redis`, `google-generativeai`, `pydantic`, `pydantic-settings`, `python-dotenv`, `pytz`, `group-lore`
- **Docker:** Python 3.11-slim, installs `group-lore` from repo root, runs `python -m app.main`

### AoE2 Match Tracker (`services/aoe2-tracker/`)

- **Tech:** Python 3.11, discord.py ≥2.3, aiohttp, pydantic-settings
- **Entry:** `app/main.py` — Initializes bot, Redis, Gemini, WorldsEdge client, starts tracker
- **Core modules:**
  - `app/tracker.py` — `AoE2Tracker`: polls WorldsEdge API for tracked players' new matches, detects group games (multiple tracked players in same match), detects friend-vs-friend matches (tracked players on opposing teams), deduplicates announcements
  - `app/bot.py` — `build_match_embed()` (Discord embed builder), `MatchView` (Discord UI with AoE2 Insights link)
  - `app/config.py` — `Settings` (pydantic-settings from env), `TRACKED_PLAYERS` dict (5 AoE2 players), `PROFILE_TO_PLAYER` reverse lookup, adaptive poll interval (10min normal, 30min off-hours 2-8am Portugal)
  - `app/civilizations.py` — Civ ID → name mapping, match type ID → name mapping
- **Services:**
  - `app/services/worldsedge.py` — WorldsEdge API client (async, aiohttp, rate-limited), `AoE2Match` and `MatchPlayer` dataclasses, profile alias resolution/caching
  - `app/services/gemini.py` — Gemini AI client for AoE2 roast generation
  - `app/services/redis_store.py` — Redis state management (per-player last match ID, per-match announcement dedup, `aoe2:` key prefix)
- **Prompts:** `app/prompts/aoe2_roast.py` — AoE2-specific system/user prompts using `group-lore` (civ picks, ELO tiers, map roasts, friend-vs-friend rivalry)
- **Tracked players:** 5 players defined in `app/config.py` (WorldsEdge profile_id): feAr, Cego, Gil, MauZaum, Paulo
- **API:** WorldsEdge API at `aoe-api.worldsedgelink.com` (no auth, successor to Relic Link API)
- **Dependencies:** `discord.py`, `aiohttp`, `redis`, `google-generativeai`, `pydantic`, `pydantic-settings`, `python-dotenv`, `pytz`, `group-lore`
- **Docker:** Python 3.11-slim, installs `group-lore` from repo root, runs `python -m app.main`

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
- **Dota 2 Bot:** Match polling, roast announcements, Nerd of the Day (`services/professor-impetus/app/config.py`)
- **WoW Bot:** M+ run polling, roast announcements (`services/wow-tracker/app/config.py`)
- **AoE2 Bot:** Match polling, roast announcements (`services/aoe2-tracker/app/config.py`)
- **Group Lore:** Shared player identities, aliases, roast instructions (`packages/group-lore/group_lore/players.py`)

When adding a new tracked player, update `packages/group-lore/group_lore/players.py` (Player entry + aliases), `apps/web/src/lib/tracked-players.ts` (Steam64 + Steam32 maps), `services/professor-impetus/app/config.py` (TRACKED_PLAYERS dict), and optionally `services/wow-tracker/app/config.py` (TRACKED_CHARACTERS dict) if they play WoW, and `services/aoe2-tracker/app/config.py` (TRACKED_PLAYERS dict + PROFILE_TO_PLAYER) if they play AoE2.

## Environment Variables

**Web** (`apps/web/.env.local`):
- `NEXT_PUBLIC_IMP_ENGINE_URL` — IMP Engine URL (default: `http://localhost:8000`)
- `NEXT_PUBLIC_GEMINI_API_KEY` — Gemini API key for AI coaching
- `NEXT_PUBLIC_STRATZ_API_TOKEN` — Stratz API token for fallback

**IMP Engine** (`services/imp-engine/.env`):
- `PORT` — Server port (default: `8000`)
- `ALLOWED_ORIGINS` — CORS origins, comma-separated or `*`

**Dota 2 Discord Bot** (`services/professor-impetus/.env`):
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

**WoW Discord Bot** (`services/wow-tracker/.env`):
- `DISCORD_TOKEN` — Discord bot token (required)
- `DISCORD_CHANNEL_ID` — Target channel ID (default: `888477897105506344`)
- `GEMINI_API_KEY` — Gemini API key (required)
- `REDIS_URL` — Redis connection URL (default: `redis://localhost:6379`)
- `POLL_INTERVAL_SECONDS` — Normal hours poll interval (default: 600)
- `OFF_HOURS_POLL_INTERVAL` — Off-hours poll interval (default: 1800)

**AoE2 Discord Bot** (`services/aoe2-tracker/.env`):
- `DISCORD_TOKEN` — Discord bot token (required)
- `DISCORD_CHANNEL_ID` — Target channel ID (default: `1112808395653775541`)
- `GEMINI_API_KEY` — Gemini API key (required)
- `REDIS_URL` — Redis connection URL (default: `redis://localhost:6379`)
- `POLL_INTERVAL_SECONDS` — Normal hours poll interval (default: 600)
- `OFF_HOURS_POLL_INTERVAL` — Off-hours poll interval (default: 1800)

## Deployment

- **Frontend:** Vercel (auto-deploys, `vercel.json` config)
- **IMP Engine:** Railway.app (Docker, healthcheck at `/health`)
- **Dota 2 Discord Bot:** Railway.app (Docker, restart on failure)
- **WoW Discord Bot:** Railway.app (Docker, restart on failure)
- **AoE2 Discord Bot:** Railway.app (Docker, restart on failure)
- **Production URLs:**
  - Frontend: `https://impetus-dota2.vercel.app`
  - IMP Engine: `https://impetus-dota2-production.up.railway.app`

## Scripts & Data

- `scripts/solve_formula.py` — Trains Ridge Regression model on Stratz samples, outputs coefficients
- `scripts/fetch_stratz_truth.py` — Fetches ground truth IMP scores from Stratz API
- `scripts/announce_v020.py` — Version announcement script
- `data/penta_role_coefficients.py` — Exported coefficients (also inline in `app/core/scoring.py`)
