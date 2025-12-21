# Impetus Architecture Plan

> **Mission:** Build an open-source Dota 2 performance analytics platform to succeed Stratz.

---

## 1. Monorepo Folder Structure

```
impetus/
├── apps/
│   └── web/                          # Next.js 14 Web Client
│       ├── public/
│       │   └── icons/
│       ├── src/
│       │   ├── app/                  # App Router pages
│       │   │   ├── (dashboard)/      # Route group for main views
│       │   │   │   ├── match/[id]/
│       │   │   │   ├── player/[id]/
│       │   │   │   └── page.tsx      # Home/Dashboard
│       │   │   ├── api/              # Next.js API routes (proxy to IMP Engine)
│       │   │   │   └── imp/
│       │   │   │       └── route.ts
│       │   │   ├── layout.tsx
│       │   │   └── globals.css
│       │   ├── components/
│       │   │   ├── ui/               # Reusable UI primitives
│       │   │   ├── charts/           # Data visualization components
│       │   │   └── match/            # Match-specific components
│       │   ├── lib/
│       │   │   ├── opendota.ts       # OpenDota API client
│       │   │   ├── imp-client.ts     # IMP Engine client
│       │   │   └── utils.ts
│       │   ├── hooks/
│       │   └── types/
│       │       └── index.ts          # Shared TypeScript types
│       ├── tailwind.config.ts
│       ├── next.config.js
│       └── package.json
│
├── services/
│   └── imp-engine/                   # Python FastAPI Microservice
│       ├── app/
│       │   ├── __init__.py
│       │   ├── main.py               # FastAPI entrypoint
│       │   ├── api/
│       │   │   ├── __init__.py
│       │   │   └── routes.py         # API route definitions
│       │   ├── core/
│       │   │   ├── __init__.py
│       │   │   ├── config.py         # Settings & environment
│       │   │   └── scoring.py        # OpenIMP scoring algorithm
│       │   ├── models/
│       │   │   ├── __init__.py
│       │   │   ├── request.py        # Pydantic request schemas
│       │   │   └── response.py       # Pydantic response schemas
│       │   └── utils/
│       │       ├── __init__.py
│       │       └── normalization.py  # Statistical normalization helpers
│       ├── tests/
│       │   └── test_scoring.py
│       ├── requirements.txt
│       ├── pyproject.toml
│       └── Dockerfile
│
├── packages/                         # Shared logic (future)
│   └── shared-types/                 # Shared type definitions
│       └── README.md
│
├── docs/
│   ├── ARCHITECTURE.md
│   └── API.md
│
├── docker-compose.yml                # Local development orchestration
├── turbo.json                        # Turborepo config (optional)
├── package.json                      # Root package.json (workspaces)
├── pnpm-workspace.yaml               # pnpm workspace config
├── PLAN.md                           # This file
└── README.md
```

---

## 2. API Contract

### Endpoint

```
POST /api/v1/calculate-imp
```

### Request Payload

The Web Client sends normalized match statistics for a single player's performance.

```json
{
  "match_id": 7890123456,
  "player_slot": 0,
  "hero_id": 74,
  "hero_name": "Invoker",
  "role": "mid",
  "duration_seconds": 2400,
  "stats": {
    "kills": 12,
    "deaths": 3,
    "assists": 18,
    "last_hits": 280,
    "denies": 15,
    "gpm": 620,
    "xpm": 685,
    "hero_damage": 32500,
    "tower_damage": 4200,
    "hero_healing": 0,
    "net_worth": 24800,
    "level": 25
  },
  "context": {
    "team_result": "win",
    "game_mode": "ranked",
    "avg_rank": 75,
    "is_radiant": true
  }
}
```

| Field             | Type    | Description                                      |
|-------------------|---------|--------------------------------------------------|
| `match_id`        | integer | Unique match identifier                          |
| `player_slot`     | integer | Player position (0-9)                            |
| `hero_id`         | integer | Dota 2 hero ID                                   |
| `hero_name`       | string  | Hero display name                                |
| `role`            | string  | `"carry"`, `"mid"`, `"offlane"`, `"support"`, `"hard_support"` |
| `duration_seconds`| integer | Match duration in seconds                        |
| `stats`           | object  | Core performance statistics                      |
| `context`         | object  | Game context for normalization                   |

---

### Response Payload

The IMP Engine returns a calculated performance score with breakdown.

```json
{
  "success": true,
  "data": {
    "match_id": 7890123456,
    "hero_name": "Invoker",
    "imp_score": 78.5,
    "grade": "A",
    "percentile": 92,
    "contributing_factors": [
      {
        "stat": "GPM",
        "value": 620,
        "deviation": "+18.2%",
        "impact": "positive",
        "weight": 0.15
      },
      {
        "stat": "KDA",
        "value": 10.0,
        "deviation": "+45.3%",
        "impact": "positive",
        "weight": 0.20
      },
      {
        "stat": "Hero Damage/min",
        "value": 812.5,
        "deviation": "+22.1%",
        "impact": "positive",
        "weight": 0.18
      },
      {
        "stat": "Deaths",
        "value": 3,
        "deviation": "-35.0%",
        "impact": "positive",
        "weight": 0.12
      },
      {
        "stat": "Last Hits/min",
        "value": 7.0,
        "deviation": "+5.2%",
        "impact": "neutral",
        "weight": 0.10
      }
    ],
    "summary": "Dominant mid performance with exceptional kill participation and economy."
  },
  "meta": {
    "engine_version": "0.1.0",
    "computed_at": "2024-01-15T14:32:00Z"
  }
}
```

| Field                  | Type    | Description                                       |
|------------------------|---------|---------------------------------------------------|
| `success`              | boolean | Request success status                            |
| `imp_score`            | float   | Normalized score (0-100)                          |
| `grade`                | string  | Letter grade: `S`, `A`, `B`, `C`, `D`, `F`        |
| `percentile`           | integer | Performance percentile (0-100)                    |
| `contributing_factors` | array   | Breakdown of each stat's contribution             |
| `summary`              | string  | AI-generated performance summary                  |

#### Grade Scale

| Grade | Score Range | Description        |
|-------|-------------|--------------------|
| S     | 90-100      | Exceptional        |
| A     | 75-89       | Excellent          |
| B     | 60-74       | Good               |
| C     | 45-59       | Average            |
| D     | 30-44       | Below Average      |
| F     | 0-29        | Poor               |

---

## 3. Walking Skeleton Roadmap

A step-by-step guide to get the "Hello World" integration running.

### Phase 0: Environment Setup

- [ ] **0.1** Initialize monorepo with `pnpm`
  ```bash
  mkdir impetus && cd impetus
  pnpm init
  echo "packages:\n  - 'apps/*'\n  - 'services/*'\n  - 'packages/*'" > pnpm-workspace.yaml
  ```

- [ ] **0.2** Create Next.js web client
  ```bash
  mkdir -p apps && cd apps
  pnpm create next-app@14 web --typescript --tailwind --eslint --app --src-dir
  ```

- [ ] **0.3** Create Python IMP Engine
  ```bash
  mkdir -p services/imp-engine/app
  cd services/imp-engine
  python -m venv venv && source venv/bin/activate
  pip install fastapi uvicorn pandas scipy numpy pydantic
  pip freeze > requirements.txt
  ```

---

### Phase 1: IMP Engine Skeleton

- [ ] **1.1** Create FastAPI entry point (`services/imp-engine/app/main.py`)
  - Health check endpoint: `GET /health` → `{"status": "ok"}`
  - Stub scoring endpoint: `POST /api/v1/calculate-imp`

- [ ] **1.2** Define Pydantic models
  - Request model matching the contract above
  - Response model matching the contract above

- [ ] **1.3** Implement mock scoring function
  - Accept any valid request
  - Return a hardcoded `imp_score: 75.0` with dummy factors
  - Validate the full response structure

- [ ] **1.4** Verify with curl
  ```bash
  uvicorn app.main:app --reload --port 8000
  curl -X POST http://localhost:8000/api/v1/calculate-imp \
    -H "Content-Type: application/json" \
    -d '{"match_id":1,"player_slot":0,"hero_id":1,"hero_name":"Anti-Mage","role":"carry","duration_seconds":1800,"stats":{"kills":5,"deaths":2,"assists":10,"last_hits":200,"denies":10,"gpm":500,"xpm":550,"hero_damage":15000,"tower_damage":2000,"hero_healing":0,"net_worth":18000,"level":22},"context":{"team_result":"win","game_mode":"ranked","avg_rank":50,"is_radiant":true}}'
  ```

---

### Phase 2: Web Client Skeleton

- [ ] **2.1** Set up Tailwind with "Cyber-Statistical" theme
  - Dark mode default
  - Neon accent colors (purple: `#A855F7`, teal: `#14B8A6`)
  - Glassmorphism utility classes

- [ ] **2.2** Create IMP Engine client (`src/lib/imp-client.ts`)
  - Function: `calculateIMP(matchStats) → IMPResponse`
  - Point to `http://localhost:8000`

- [ ] **2.3** Create API proxy route (`src/app/api/imp/route.ts`)
  - Forward requests to IMP Engine
  - Handle CORS and errors

- [ ] **2.4** Build minimal test page (`src/app/page.tsx`)
  - Button: "Calculate IMP Score"
  - On click: Send dummy match data to API
  - Display: `imp_score` and `grade` in a styled card

---

### Phase 3: Integration Test

- [ ] **3.1** Run both services
  ```bash
  # Terminal 1: IMP Engine
  cd services/imp-engine && uvicorn app.main:app --reload --port 8000
  
  # Terminal 2: Web Client
  cd apps/web && pnpm dev
  ```

- [ ] **3.2** Verify end-to-end flow
  - Open `http://localhost:3000`
  - Click "Calculate IMP Score"
  - Confirm score card displays with `75.0` and grade `A`

- [ ] **3.3** Document in README
  - Quick start commands
  - Environment variables
  - Architecture diagram link

---

### Phase 4: Real Algorithm (Next Iteration)

> **Out of Scope for Walking Skeleton**

- [ ] Implement actual OpenIMP scoring algorithm
- [ ] Add role-based stat weighting
- [ ] Integrate OpenDota match fetching
- [ ] Add hero-specific normalization curves

---

## 4. Development Commands Cheatsheet

| Task                     | Command                                           |
|--------------------------|---------------------------------------------------|
| Install all deps         | `pnpm install`                                    |
| Run web client           | `cd apps/web && pnpm dev`                         |
| Run IMP engine           | `cd services/imp-engine && uvicorn app.main:app --reload` |
| Run both (Docker)        | `docker-compose up`                               |
| Run engine tests         | `cd services/imp-engine && pytest`                |

---

## 5. Next Steps After Walking Skeleton

1. **OpenDota Integration** - Fetch real match data
2. **Scoring Algorithm V1** - Implement statistical normalization with Scipy
3. **Match Detail Page** - Visualize score breakdown with charts
4. **Player Profile Page** - Trend analysis over multiple matches
5. **Deployment** - Vercel (web) + Railway/Fly.io (engine)

---

*Document Version: 1.0*  
*Last Updated: 2024-12-21*
