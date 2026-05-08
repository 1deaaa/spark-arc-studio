# Matchbox Agent Gateway: Embedded LLM Gateway for Agent Systems

[简体中文](README.md) | [English](README.en.md) | [日本語](README.ja.md)

Matchbox is a full-featured gateway designed for agent-native applications.
It is embedded directly into your app runtime, so model routing, key isolation, quotas, and usage analytics all happen where your agents run.

---

## Product Positioning

Matchbox is built for teams that need both:

- Fast local/prototyping workflows
- Production-grade multi-user governance

Instead of introducing an external gateway as another independent platform, Matchbox keeps AI operations inside the same codebase and lifecycle as your application.

---

## Why Embedded (vs External Gateway)

### 1. Agent-Orchestration Native

- Works naturally with LangChain/LangGraph patterns
- Preserves context/tool metadata through the application layer
- Reduces multi-hop latency and protocol mismatch risk in streaming chains

### 2. Unified Key Strategy

- Supports system-managed hosted keys
- Supports BYOK per user
- Supports hybrid fallback strategy via `LLM_AUTO_KEY`

### 3. Quota Governance That Matches Real Billing

Calls are split by actual funding source:

- `sys_paid`: uses hosted system key
- `self_paid`: uses user-owned key

Each scope can have independent window limits and total limits.

### 4. Lower Ops Overhead

- No extra Redis/OneAPI stack required
- SQLite + SQLAlchemy persistence
- GUI management tool included

---

## Core Capabilities

- Multi-user platform/model management
- Usage slots: `main`, `fast`, `reason`, plus custom slots
- API key encryption at rest
- Dynamic model probing for OpenAI-compatible providers
- Reasoning-stream compatibility normalization
- Usage tracking and account-level statistics
- GUI-based administration (`matchbox_cfg_gui.py`)

---

## Runtime Model

Matchbox uses two practical paths.

### Path A: Managed path (recommended)

Use this for normal application traffic.

```python
from llm.agen_matchbox import initialize_matchbox, matchbox

initialize_matchbox(ensure_defaults=True)
client = matchbox().get_user_llm(user_id='user_123', usage_key='main', agent_name='agent_director')
result = client.invoke('Generate a cyberpunk world seed')
```

What you get automatically:

- User selection resolution
- Key priority resolution
- Quota checks before provider call
- Usage accounting

### Path B: Quick path (bypass)

Use for scripts and temporary tooling where DB coupling is unnecessary.

- `create_quick_llm(...)`
- `create_quick_embedding(...)`

---

## Key Concepts

### System user

`SYSTEM_USER_ID = "-1"` represents backend/system-level calls.

### Global mode switch

- `USE_SYS_LLM_CONFIG = True`: users consume system-defined platforms/models
- `USE_SYS_LLM_CONFIG = False`: users can add/manage private platforms/models

### Fallback switch

- `LLM_AUTO_KEY = True`: allow system fallback key when user key is missing
- `LLM_AUTO_KEY = False`: fail fast if user key is required but missing

### Quota scopes

Quota policy is evaluated on actual key path:

- `sys_paid` limits apply only to hosted-key calls
- `self_paid` limits apply only to user-key calls

This prevents hosted budget exhaustion from blocking user self-paid traffic.

---

## Data Source Strategy

Matchbox uses a dual-source model with clear authority.

- Runtime source of truth: `llm_config.db`
- Bootstrap/incremental sync/export: `matchbox_cfg.yaml`

Important:

1. YAML initializes structures; runtime reads from DB.
2. GUI edits write directly to DB.
3. If historical `ENC:` keys cannot be decrypted in a new environment, platform/model structures still sync; replace keys locally.

---

## First-Time Setup (Recommended)

1. Run GUI tool:

```bash
python matchbox_cfg_gui.py
```

2. Set `LLM_KEY` (master encryption key)
3. Fill real API keys for target platforms
4. Probe models and test connectivity
5. Bind `main` / `fast` / `reason` usage slots

---

## Security Guidelines

- Do not commit plaintext API keys
- Prefer environment variables + encrypted DB storage
- Keep `.env` private
- Rotate hosted keys on environment migration

---

## Operational Notes

- Initialize Matchbox in app startup lifecycle
- Call `reset_matchbo()` on shutdown when needed
- Use `AGENT_MATCHBOX_HOME` to control runtime files (DB/.env/YAML/state) location
- Rebuild containers after updates to avoid stale mounted runtime artifacts

---

## Related Docs

- Main contribution docs:
  - `CONTRIBUTING.zh-CN.md`
  - `CONTRIBUTING.en.md`
  - `CONTRIBUTING.ja.md`
- Main project docs:
  - `../../../../README.md`
  - `../../../../README.en.md`
  - `../../../../README.ja.md`

Matchbox focuses on one goal: deliver reliable, governable LLM access for agent-first products without adding unnecessary deployment complexity.

---

## License

Matchbox Agent Gateway is separately licensed under Apache License 2.0 according to the `LICENSE` file in this directory and may be reused as an independent component.

This license applies only to the components explicitly covered inside `server/llm/agen_matchbox` and does not change the AGPL-3.0-only license of the rest of the SparkArc main project.
