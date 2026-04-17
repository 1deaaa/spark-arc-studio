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

### 4.1 Agent Tri-Mode Prompt Protocol (Mandatory, see AGENTS.md §4.5)
Every specialist agent's `server/agents/prompts/<agent>.yaml` must define three top-level fields for the three invocation modes:

| Mode | Entry Path | YAML Field | Audience |
| :--- | :--- | :--- | :--- |
| Specialized Work | Business route / panel button → `agent.execute()` / named method | `system` + `user` | Machine parsers |
| Chat Mode | `chat_stream(skip_tool_confirmation=False)` | `chat_system` | End users |
| Pipeline Mode | Director `delegate_task` → `sub_agent_node` → `chat_stream(skip_tool_confirmation=True)` | `pipeline_system` | The director (upstream agent) |

Hard rules for `pipeline_system`:
- **Audience declaration**: The first sentence must state "your audience is the director, not the user".
- **Three-part core**: Write only「call tool + one-shot output + brief report to director」. No more.
- **Format spec via tool reference, not copy-paste**: Structural output specs should be bound to the persistence tool's yaml `system` field via `_get_tool_prompt_references()`, not duplicated inside `pipeline_system` — that causes dual-maintenance drift. See AGENTS.md §4.5.1.
- **No dangling references**: Never write "same as normal generation" or "format identical to system". The two system fields are mutually exclusive in code; the LLM cannot see the other field.
- **No brainstorming softening**: Never add "diverge / break conventions / be passionate" style modifiers that conflict with structured output.
- **Exception — agents without persistence tools** (e.g. critic, whose output goes straight to the director): `pipeline_system` must inline the key output spec summary (field list, grading criteria, etc.) rather than referencing `system`.

`chat_system` carries conversational persona only and imposes no strict output format. `system` holds the strictest structural spec. Violating any rule above causes mode confusion (e.g. director-delegated Muse starts world-building — a real historical bug caused by missing tool reference registration, which dropped all 7 format constraints in pipeline mode).

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
