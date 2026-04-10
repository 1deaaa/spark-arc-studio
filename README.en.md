# SparkArc: Cross-Platform Agent Studio for Story Creation

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

SparkArc is a production-grade creative studio powered by coordinated Agents.
It helps creators turn a tiny spark into a complete story world and publishable output across:

- Novel drafting
- Scriptwriting
- Interactive web performance
- Game-engine-ready story assets

SparkArc connects the full chain:

`Inspiration -> Worldbuilding -> Rhythm -> Outline -> Drafting -> QA -> Publish -> Share -> Performance`

---

## Why SparkArc

Most AI writing tools are either:

- A black-box text generator with weak structure control
- A complex prompt playground that shifts workflow burden back to the user

SparkArc takes a different product direction:

1. You communicate naturally with a Director Agent.
2. The Director dispatches specialized Agents and tools.
3. Structured editors stay in sync with generated outputs.
4. You can intervene at any layer without losing flow.

Result: you get IDE-level production power with chat-level simplicity.

---

## Product Pillars

### 1. Studio UX for Serious Creation

- Multi-agent orchestration behind a single conversation entry
- Structured editors for world, synopsis, outline, and script layers
- Traceable generation process instead of one-shot black-box output
- Surgical refinement by specialist Agent when a section needs rework

### 2. Human-Centered Control

SparkArc treats human creativity as the source of truth.

- `Manual mode`: AI assists with checks and suggestions
- `Hybrid mode` (recommended): AI expands details while you keep narrative control
- `Auto mode`: AI explores directions from a rough concept

### 3. Quality and Consistency Loop

- `Style Agent`: style cloning to reduce generic AI phrasing
- `Critic Agent`: evidence-based editorial review (S/A/B/C/D tiers)
- `GraphRAG`: cross-document fact constraints for long-form consistency

### 4. Mobile-to-Desktop Continuity

- Mobile-friendly flow for commuting and fragmented sessions
- Desktop studio for deep editing and system-level management
- Inspiration inbox via MCP for cross-tool idea capture

### 5. Performance-Ready Outputs

- Share stories through web performance links
- Keep a clear upgrade path to game engine integration
- Treat scripts as executable content assets, not static documents

### 6. Scalable Agent Operations

SparkArc defines collaboration semantics with:

- `Beacon`: visibility/receivability
- `Horn`: proactive communication permission
- `Baton`: ownership of current task chain

This model reduces multi-agent chaos and keeps large flows maintainable.

---

## Agent Pipeline (Production View)

| Stage | Industry Parallel | Agent / Tool | What it does |
| :-- | :-- | :-- | :-- |
| 0. Orchestration | Director Room | `Director` | Intent routing, context continuity, interaction entry |
| 1. Ideation | High Concept | `Muse` | Captures seed ideas and expands them into creative directions |
| 2. Worldbuilding | Story Bible | `Lorebook` | Builds world rules, settings, and character foundations |
| 3. Structure | Beat Sheet | `Showrunner` | Generates beats and chapter/scene skeletons |
| 4. Drafting | Screenplay Draft | `Scriptwriter` + `GraphRAG` | Produces scene-level script while honoring fact constraints |
| 5. QA | Script Doctor | `Critic` + `Style` + `GraphRAG` | Detects weak spots, AI flavor residue, and continuity issues |
| 6. Delivery | Runtime Assets | Web Player / Unity SDK | Converts script output into interactive, runnable experiences |

---

## Architecture at a Glance

### Backend convergence points

- Communication base: `server/agents/communication.py`
- Execution protocol: `server/agents/agent_utils.py`
- Tool facade: `server/agents/agent_tools.py`
- Multi-agent scheduling: `server/agents/director_graph.py`
- Streaming bridge: `server/agents/routes/streaming_utils.py`
- Semantic stream runtime: `server/agents/routes/stream_semantics.py`

### Frontend convergence points

- Streaming runtime: `client/src/utils/streamingRuntime.ts`
- Chat sink: `client/src/components/stores/chatStore.ts`
- Global loading UI: `client/src/components/share/GlobalLoading.vue`
- Event bus: `client/src/eventBus.ts`

### Two stream protocols (important)

- Chat chain: NDJSON events (`assistant_delta`, `tool_*`, `reasoning_delta`)
- Business chain: semantic SSE (`onStart`, `onDelta`, `onDone`, ...)

They are intentionally separate and should not be mixed.

---

## Quick Start

### Option A: Docker (recommended)

```bash
git clone https://github.com/your-repo/sparkarc.git
cd sparkarc
docker compose up -d --build
```

Open: http://localhost:7788

After every `git pull`, use rebuild instead of restart:

```bash
git pull --ff-only
docker compose up -d --build --force-recreate
docker compose logs --tail=120 sparkarc
```

Why: this guarantees fresh code and avoids old mounted files masking new behavior.

### Option B: Local development

1. Create Python env and install server dependencies
2. Build frontend in `client/`
3. Start backend in `server/`
4. Open http://localhost:6688

---

## Localization and Language Policy

- UI locales: `zh-CN`, `en-US`, `ja-JP`
- Frontend language is switchable in Settings
- Agent system prompts apply a unified locale policy:

1. Prioritize current locale by default
2. Switch only when user proactively uses another language or explicitly requests a switch

For frontend contributions: avoid hardcoded user-visible strings and use Vue I18n.

---

## Repository Guides

- Main contribution guides:
  - `CONTRIBUTING.zh-CN.md`
  - `CONTRIBUTING.en.md`
  - `CONTRIBUTING.ja.md`
- Agent constraints and architecture rules: `AGENTS.md`
- Agent language policy note: `agent.md`

---

## Matchbox Gateway

SparkArc bundles Matchbox in `server/llm/agen_matchbox`.

Matchbox provides model routing, key management, quota governance, and usage telemetry for agent workloads.

Read more:

- `server/llm/agen_matchbox/README.md`
- `server/llm/agen_matchbox/README.en.md`
- `server/llm/agen_matchbox/README.ja.md`

---

## Product Roadmap (directional)

- Style-consistent character portrait pipeline
- Lightweight background art generation/editing workflow
- User-defined scriptwriter capability packs (specialist sub-agents)
- Data-driven custom UI components generated from schema contracts

SparkArc is built to make high-quality narrative production more accessible, repeatable, and creator-led.
