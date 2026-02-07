# Life Kiosk Film Design (Sentinel)

Date: 2026-02-07
Status: Validated brainstorm design

## Goal
Build a non-interactive arcade/adventure "film" app in `life/` that runs in kiosk mode and visualizes Sentinel portfolio behavior through continuous 2D storytelling. The experience has no words, no sound, and no user input. It should be beautiful, durable for long-term viewing, and safe for monitor retention.

## Confirmed Direction
- Platform/runtime: Go + Bubble Tea, terminal-only
- Visual language: Classic retro platformer grammar with painterly pixel-art atmosphere
- Display target: 1024x600
- Motion model: Auto side-scroll
- Constraint: Character is not permanently centered (anti-burn-in)
- Signal model: Hybrid (portfolio state + trade/rebalance events)
- Intensity model: Continuous 0..100
- Data integration: Read-only Sentinel API polling
- World model: Handcrafted objects in a procedural world
- Stream unit: Tile columns
- Difficulty/readability: Intensity changes density and mood, not failure risk (character always succeeds)
- Anti-retention strategy: Multi-layer drift
- Signal visibility: Subtle
- Performance baseline: 30 FPS cap initially, downshiftable if needed

## 1) Core Runtime Architecture
`life/` is a standalone Go module acting as a deterministic film simulator.

Primary subsystems:
- `world`: Endless tile-column streaming using handcrafted motifs and procedural placement rules.
- `actor`: Deterministic traversal scripts (run, jump, collect, avoid) with guaranteed success.
- `camera`: Continuous side-scroll with drifting framing window and safe composition bounds.
- `director`: Maps Sentinel signals to continuous intensity/mood controls.
- `render`: Produces terminal frames with parallax layers, silhouette-first readability, and palette modulation.

Suggested package boundaries:
- `life/internal/sim`: Pure state transitions and fixed-step update loop
- `life/internal/io/sentinel`: Polling client, retries, caching, normalization
- `life/internal/render`: Terminal draw pipeline
- `life/internal/config`: Tunables and profiles (fps/effects/degrade tiers)

Reliability principle: Sentinel input enriches behavior but simulation progress never depends on live API availability.

## 2) Signal Mapping And Procedural Composition
Data polling (example cadence: every 5 seconds) reads existing Sentinel endpoints such as:
- `/api/unified`
- `/api/planner/summary`
- `/api/portfolio`
- `/api/jobs/history`

A smoothed `intensity` score in `0..100` is derived from blended signals:
- Portfolio movement/variance
- Allocation drift pressure
- Trade/rebalance activity freshness
- Market context (open/closed state)

Intensity effects (subtle, non-literal):
- Object density up/down (coins, obstacles, props)
- Rhythm and spacing shifts
- Mood modulation (palette temperature, contrast, haze, parallax ratio, sparkle frequency)

World generation rules:
- Tile-column streaming with weighted rule packs
- Handcrafted object catalog drives aesthetics
- Procedural selection controls frequency and arrangement
- Constraints enforce beauty/readability:
  - Landing visibility floor
  - Silhouette spacing minimums
  - Coin arc coherence
  - Obstacle rhythm caps
  - Forbidden harsh combinations

Outcome: high long-term variation without incoherent or noisy scenes.

## 3) Camera Drift, Anti-Burn-In, And Cinematic Pacing
Camera and retention safety:
- Side-scroll baseline with soft-follow framing window
- Slow drift of framing window across safe bounds
- Independent background focal drift
- Bright-region redistribution over time (coins/highlights/FX)
- No static HUD; any score motif is transient and relocates
- Luminance centroid wandering to avoid persistent hotspots

Cinematic pacing:
- Deterministic micro-arcs (traverse -> rise -> collect flourish -> weave -> resolve -> breathe)
- Intensity stretches/compresses arc timing
- Calm periods: wider feel and more breathing room
- Active periods: denser rhythm and slightly stronger lead
- Long-horizon cadence phase shifts to prevent short-loop fatigue

## 4) Error Handling, Reliability, Testing, Delivery
Input health states:
- `fresh`, `stale`, `offline`
- Failures never pause simulation
- On stale/offline, mood/intensity gracefully decay toward neutral

Resilience mechanics:
- Timeout budgets, exponential backoff, jittered retries
- Per-field payload tolerance (ignore malformed fields)
- Runtime degrade tiers under pressure:
  - Reduce background complexity
  - Reduce effect density
  - Lower FPS cap if needed

Verification strategy:
- Unit tests for simulation/rules
- Deterministic snapshot tests for generated columns and actor trajectories
- Property tests for traversability guarantees
- Contract tests for Sentinel payload variability
- Long-run soak tests for deadlock/memory/frame pacing stability
- Lightweight visual regression via seeded frame hashes

Delivery phases:
1. Scaffold `life/` app, fixed-step loop, renderer, side-scroll actor
2. Add tile-column procedural world + handcrafted object catalog
3. Integrate Sentinel polling and continuous intensity/mood mapping
4. Add anti-burn-in drift, degrade tiers, soak tests, kiosk startup/restart scripts

## Open Decisions To Resolve During Implementation Planning
- Exact ASCII/cell rendering strategy for painterly feel in terminal constraints
- Endpoint field weighting for initial intensity formula
- Seed and cadence tuning targets for 8h/24h aesthetic variation
- Preferred supervisor setup for always-on kiosk process management
