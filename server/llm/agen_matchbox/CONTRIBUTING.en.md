# Matchbox Gateway Contributing Guide

## 1. Scope

This guide applies to the `server/llm/agen_matchbox` subproject. The goal is to keep multi-user routing, quota enforcement, key security, and agent compatibility stable across changes.

## 2. Core Principles

- **DB is the runtime authority.** YAML (`matchbox_cfg.yaml`) is only used for bootstrap/incremental sync/export. All business reads go to `llm_config.db`.
- **Preserve the unified call chain:** `initialize_matchbox()` -> `matchbox()` -> `get_user_llm(...)` / `get_spec_sys_llm(...)`.
- **Light init, heavy warmup:** `initialize_matchbox()` must remain lightweight (DB schema + default config sync only). Heavy runtime deps (`langchain_openai`, `ChatUniversal`, `LLMClient`) are loaded via `warmup_matchbox_runtime()` or lazy-loaded inside `_load_chat_runtime()` at first use.
- **Keep quota scopes separated:** `sys_paid` (hosted key) and `self_paid` (user key) must remain independent tracks.
- **Never commit secrets:** No plaintext API keys, `.env` files, or private config material in commits.

## 3. Initialization Architecture

The package exposes a two-phase startup model. Understanding this is essential before modifying init-related code:

### Phase 1: `initialize_matchbox()` (lightweight)

Creates the `AIManager` singleton, sets up DB engine/session, syncs YAML defaults to DB, and resolves default platform/model IDs. This phase intentionally does **not** import `langchain_openai`, `ChatUniversal`, or any heavy SDK modules.

### Phase 2: `warmup_matchbox_runtime()` (heavy, non-blocking)

Pre-imports `.gateway` and `.tracked_model` in a background thread so that the first `get_user_llm()` call does not block on module loading. Callers can pass `blocking=True` if synchronous warmup is needed (e.g., test scripts).

### Skip conditions

- `SPARKARC_SKIP_LLM_MANAGER=1` disables the manager entirely (returns `None`).
- When `sys.argv` contains `alembic` or `gen_migration.py`, the manager is auto-skipped to avoid migration deadlocks.

## 4. Recommended Change Patterns

- **Extend, don't duplicate:** Add new functionality via `manager.py` mixins rather than copying logic into route handlers.
- **Model changes follow Alembic workflow:** Run `cd server && alembic upgrade head -x db=llm` for schema changes. Keep `Base.metadata.create_all()` as a fallback for non-Alembic environments.
- **GUI and API semantics must align:** Platform, model, usage slot, and quota policy changes must be reflected in both `gui/` panels and REST API responses.
- **Lazy-load heavy deps:** Any new module that depends on `langchain_openai`, `tiktoken`, or similar heavy packages should follow the `_load_chat_runtime()` pattern in `builder.py` — load on first call, not at import time.

## 5. Agent Ecosystem Compatibility

- This gateway is the runtime foundation for agents. Preserve LangChain/LangGraph compatibility.
- Do not break function-calling, streaming behavior, or reasoning field normalization (`ChatUniversal` in `gateway.py`).
- The `LLMClient` wrapper must remain directly usable as an LLM (`client.invoke()`, `client.stream()`).
- If default behavior changes, update README and usage examples in the same PR.

## 6. Key Files Reference

| File | Responsibility |
|------|---------------|
| `__init__.py` | Package entry: `initialize_matchbox`, `warmup_matchbox_runtime`, `matchbox`, lazy exports |
| `manager.py` | `AIManager` core class (all mixins composed) |
| `config.py` | Constants (`USE_SYS_LLM_CONFIG`, `LLM_AUTO_KEY`, `SYSTEM_USER_ID`), YAML/env loading |
| `builder.py` | `LLMBuilderMixin` — resolves user choice, builds `LLMClient` |
| `gateway.py` | `ChatUniversal` (reasoning-aware ChatOpenAI subclass), `create_quick_llm/embedding` |
| `tracked_model.py` | `LLMClient`, `LLMUsage`, `UsageTrackingCallback` |
| `models.py` | SQLAlchemy schema (platforms, models, usage slots, quota policies) |
| `security.py` | `SecurityManager` — Fernet encryption for API keys |
| `quota_services.py` | `sys_paid`/`self_paid` quota enforcement |
| `usage_services.py` | Time-series usage logging and aggregation |
| `credit_services.py` | Credit balance management and enforcement |

## 7. Pre-PR Checklist

- [ ] No sensitive keys or private data committed.
- [ ] `initialize_matchbox()` remains lightweight — no heavy SDK imports at this stage.
- [ ] `warmup_matchbox_runtime()` is called by host applications (not by the library itself).
- [ ] User model selection and usage-slot behavior remain compatible.
- [ ] Quota accounting and charging flows still work as expected.
- [ ] New code follows the lazy-loading pattern for heavy dependencies.
- [ ] Documentation is updated accordingly.
