# Matchbox Gateway Contributing Guide (English)

## 1. Purpose
This guide applies to the subproject at server/llm/agen_matchbox. Keep multi-user routing, quota behavior, key security, and agent compatibility stable.

## 2. Core Principles
- Runtime source of truth is the database; YAML is mainly for bootstrap/export.
- Preserve the unified call chain: initialize_matchbox(...) -> matchbox() -> get_user_llm(...).
- Keep quota scopes `sys_paid` and `self_paid` clearly separated.
- Never commit plaintext API keys, .env files, or private config material.

## 3. Recommended Change Pattern
- Prefer extending manager.py and mixins instead of duplicating logic across routes.
- If data models change, follow the main project migration workflow.
- Keep GUI and backend API semantics aligned (platforms, models, usage slots, quota policies).

## 4. Agent Ecosystem Compatibility
- This gateway is the runtime foundation for agents; preserve LangChain/LangGraph compatibility.
- Do not break function-calling, streaming behavior, or reasoning field normalization.
- If default behavior changes, update README and usage examples in the same PR.

## 5. Pre-PR Checklist
- No sensitive key or private data is committed.
- User model selection and usage-slot behavior remain compatible.
- Quota accounting and charging flows still work as expected.
- Documentation is updated accordingly.
