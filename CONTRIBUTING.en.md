# SparkArc Contributing Guide (English)

## 1. Purpose
This guide applies to contributions in the main project. Read it together with AGENTS.md and follow the unified pipeline rules first.

## 2. Architecture Guardrails
- Chat pipeline: frontend must go through chatStore; backend must go through server/agents/routes/chat.py + SparkBaseAgent.chat_stream.
- Business streaming pipeline: frontend must use createStreamingTask; backend must use stream_semantics + iterate_sync_iterable_in_thread.
- Tool extensions: register tools in server/agents/agent_tools.py. Do not implement ad-hoc tool protocols in routes or single agents.
- Database changes: update models and generate migrations via server/gen_migration.py only. No manual migration files.

## 3. Frontend Rules (Mandatory)
- Do not hardcode any user-visible text.
- All user-visible strings must use Vue I18n.
- Every new feature must provide translations for zh-CN / en-US / ja-JP.
- For chat or streaming changes, reuse existing integration points:
  - client/src/components/stores/chatStore.ts
  - client/src/utils/streamingRuntime.ts

## 4. Agent and Prompt Rules
- Maintain prompts through unified entries first: server/agents/agent_utils.py (load_prompt) and SparkBaseAgent system prompt assembly.
- Language policy: Agents must prioritize the selected language by default, and switch only when users proactively use another language or explicitly request a language change.
- Avoid duplicating the same prompt rule in multiple agents. Prefer centralized injection.

## 5. Testing and Validation
For chat pipeline, multi-agent, tool visualization, or semantic streaming changes, run at least:
- server/test/test_chat_stream_events.py
- server/test/test_chat_history_segments.py
- server/test/test_tool_event_ui_metadata.py
- server/test/test_director_graph.py
- server/test/test_stream_semantics_runtime.py
- client/src/components/stores/__tests__/chatStore.spec.ts
- client/src/utils/__tests__/streamingRuntime.spec.ts

## 6. Pre-PR Checklist
- Integrated with existing unified pipelines (no parallel implementation).
- No hardcoded UI text remains in touched areas.
- zh-CN / en-US / ja-JP entries are complete.
- Required tests and manual regression were performed.
