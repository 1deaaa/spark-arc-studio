# SparkArc Contributing Guide (English)

## 1. Goal & Position
This guide serves as the authoritative contributing guide for the SparkArc main project. Due to the massive scale of the project and its multi-agent collaboration system, all contributors (including human developers and AI coding assistants) **must read this guide together with [AGENTS.md](file:///d:/Desktop/sparkarc/AGENTS.md)** before writing or modifying any code.
We strictly adhere to the fundamental principle of **"unified integration, no duplicated implementations"**: before developing any new feature, check whether a Facade, Pipeline, or unified infrastructure already exists in the system that can accommodate the logic. Parallel pipelines or reinventing the wheel is strictly prohibited.

## 2. Core Architecture & Dual Pipelines
SparkArc's streaming response system is divided into two distinct pipelines with clear boundaries. Mixing event protocols or consumer states between the two pipelines is strictly prohibited.

### 2.1 Chat Pipeline (Chat NDJSON)
- **Purpose**: Free-form conversation, Agent delegation/handoff interactions, and tool visualization.
- **Frontend Entry**: [chatStore.ts](file:///d:/Desktop/sparkarc/client/src/components/stores/chatStore.ts) (where `_consumeStream` consolidates stream parsing and manages chronological Segments).
- **Backend Entry**: [chat.py](file:///d:/Desktop/sparkarc/server/agents/routes/chat.py) route + [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py) (`SparkBaseAgent.chat_stream`).
- **Key Facts**:
  - The stream transmission format is NDJSON (containing events such as `task_snapshot`, `assistant_delta`, `reasoning_delta`, `tool_*`, `task_done`, etc.).
  - Chat states and history are restored using an incremental Event Log Checkpoint model. Reconnection or page-refresh recovery must use `task_snapshot` and cursor-based replay. Using Progress Queue for replay or relying on destructive reading interfaces like `get_nowait` is **strictly forbidden**.

### 2.2 Business Streaming Pipeline (Business SSE / Semantic Stream)
- **Purpose**: Long-running business tasks (e.g., voice/style cloning, Muse inspiration, lorebook generation, outline structure, scriptwriter generation, etc.).
- **Frontend Entry**: [streamingRuntime.ts](file:///d:/Desktop/sparkarc/client/src/utils/streamingRuntime.ts) (uses `createStreamingTask` to manage task lifecycle and global loading mask).
- **Backend Entry**: [streaming_utils.py](file:///d:/Desktop/sparkarc/server/agents/routes/streaming_utils.py) (uses `iterate_sync_iterable_in_thread` to bridge synchronous generators to async responses).
- **Key Facts**:
  - Adheres to the standard semantic frame protocol, attaching event frames such as `onStart`, `onProgress`, `onDelta`, `onStats`, `onDone`, `onError`, and `onCancelled`.
  - The frontend must not implement custom "cancel + stats" state machines in components; all business streams must be hosted through `createStreamingTask`.

## 3. Unified Infrastructure Bases
To ensure the long-term maintainability of the project and avoid duplicated code blocks, SparkArc provides the following unified infrastructures. Any similar functional requirements **must reuse** these components, and writing custom local logic is strictly prohibited:

1. **Local Replacement & Patching (Patch)**:
   - Centrally handled by the `_apply_patch` function in [common.py](file:///d:/Desktop/sparkarc/server/agents/tools/common.py). Whether performing script rewriting, outline updates, or worldview setting changes, the logic of locating and replacing text must delegate to this function. Do not write custom regular expressions or string `.replace()` calls.
2. **Token Chunking (Token Chunking)**:
   - Centrally handled by `TokenTextSplitter` in [chunking.py](file:///d:/Desktop/sparkarc/server/core/file_ingest/chunking.py). Any logic that splits text based on Token count must reuse this component.
3. **Semantic Chunker (Semantic Chunker)**:
   - Centrally handled in [SemanticChunker](file:///d:/Desktop/sparkarc/server/story/semantic_chunker/) directory. Semantic chunking for project files, knowledge graphs, and vector indexing must reuse this engine.
4. **Infrastructure Extension Principle**:
   - Any future underlying infrastructure that is likely to be reused across multiple places (e.g., vector search, caching control, document parsing) must first be extracted to the common tools layer or core service layer, and must not be duplicated in business routes or individual agents.

## 4. Backend Extensions & Agent Modality Contract
Adding new agents or extending tools must follow a rigorous registration and contract pipeline:

### 4.1 New Agent Registration Checklist
1. **Base Reuse**: Inherit from `SparkBaseAgent` (for communication and chat) and `SparkAgentExecutor` (for the execution protocol).
2. **Four Registration Hook Points**:
   - [registry.py](file:///d:/Desktop/sparkarc/server/agents/registry.py): Register agent metadata.
   - [runtime.py](file:///d:/Desktop/sparkarc/server/agents/routes/runtime.py): Register route lock strategies and signals.
   - [agent_tools.py](file:///d:/Desktop/sparkarc/server/agents/agent_tools.py) & [tools/registry.py](file:///d:/Desktop/sparkarc/server/agents/tools/registry.py): Register and bind tools to the agent.
   - [director_graph.py](file:///d:/Desktop/sparkarc/server/agents/director_graph.py): Configure whether the agent can be delegated tasks by the Director.

### 4.2 Agent Tri-Mode Prompt Protocol
Every specialist agent must implement exactly three invocation modalities to prevent mode confusion:
- **Specialized Work Mode**: Triggered by `agent.execute()`. Uses the YAML `system` + `user` fields. The output format is extremely strict, intended for machine parsing/direct file persistence, and conversational fluff is strictly prohibited.
- **Chat Mode**: Triggered by chat routes. Uses the YAML `chat_system` field. Intended for end users, allowing natural dialogues and brainstorm suggestions.
- **Pipeline Mode**: Triggered by Director delegation. Uses the YAML `pipeline_system` field. Intended for the upstream director agent.

#### Prompt Architecture & Single Source of Truth Rules
1. **Tool Reference Injection**:
   - Use `_get_tool_prompt_references()` to bind format specifications to the YAML `system` field of the corresponding persistence tool. The `pipeline_system` prompt must remain extremely minimal (declaring only audience, tool calls, and report-back), and copying format specifications into `pipeline_system` is strictly prohibited.
2. **Shared Prompt Base (`base` field)**:
   - Shared personas or core guidelines must be defined in the YAML's top-level `base` field and referenced using `{base.xxx}` placeholders in individual modes to avoid duplicated maintenance.
3. **Supplement Rules (`tool_rules` field)**:
   - Tool execution order, output purity, and anti-injection requirements specific to an agent must be placed in the YAML's `tool_rules` field. These are automatically appended by the base class. Do not hardcode tool rules in Python.

## 5. Frontend Extensions & Internationalization (I18n)
1. **Unified UI Stream Events**:
   - Tool execution UI metadata (`ui_scope` / `ui_target` / `ui_refresh_events`) must be injected by the backend `build_tool_stream_event` in [communication.py](file:///d:/Desktop/sparkarc/server/agents/communication.py). The frontend must read this from `chatStore` directly. Hardcoding UI refresh triggers inside frontend components is strictly prohibited.
2. **Frontend Mapping Self-Check checklist**:
   - When modifying/adding agents, check if the following UI maps need updates:
     1. Default Assignee: [GlobalChatFloat.vue](file:///d:/Desktop/sparkarc/client/src/components/share/GlobalChatFloat.vue) (`viewAgentMap`).
     2. Bubble Style: [useAgentRegistry.ts](file:///d:/Desktop/sparkarc/client/src/composables/useAgentRegistry.ts) (`agentIconMap`/`agentColorMap`/`agentNameMap`).
     3. Flow Blueprint: [AgentFlowBlueprint.vue](file:///d:/Desktop/sparkarc/client/src/components/lorebook/AgentFlowBlueprint.vue).
     4. Mock Data: `agentRuntimeStore.ts`.
     5. Settings Panel: `AiSettingsPanel.vue`.
3. **Vue I18n Constraints**:
   - **No hardcoded text** is allowed for user-visible strings. All UI strings must be fully translated and synced across `zh-CN`, `en-US`, and `ja-JP` locale files.

## 6. Database & Migration Rules
1. **No Manual Migration Edits**:
   - All database schema changes must be declared in [models.py](file:///d:/Desktop/sparkarc/server/core/models.py). Run the auto-generator command:
     `python server/gen_migration.py`
     Migrations are executed automatically on application startup via [auto_migrate.py](file:///d:/Desktop/sparkarc/server/core/auto_migrate.py).

## 7. Core Architectural Anti-Patterns (Prohibitions)
The following coding behaviors are considered **severe architectural violations**:
1. **Pipeline Duplication**: Copying stream bridging logic across routes instead of utilizing `streaming_utils.py`.
2. **Bypassing Loading Mask**: Controlling global loading overlays manually or emitting loading events directly without using `createStreamingTask`.
3. **Bypassing Stream UI Injection**: Handling tool state machines or refresh maps in frontend components instead of using `build_tool_stream_event`.
4. **Mixing Stream Protocols**: Bridging `NDJSON` directly into SSE frames or pushing SSE events straight to `chatStore`.
5. **Direct IO Path Bypassing**: Defining direct physical paths for output files in agents instead of using the unified `write_result` exit.
6. **Ghost Registrations**: Creating agents/tools without updating `registry.py` and facade files.
7. **Manual DDL Execution**: Executing manual SQL statements in database upgrades rather than generating migrations.
8. **Git Repository Pollution**: Writing runtime temporary files (e.g., caches, FAISS vectors, pickle serialized artifacts, intermediate JSON) directly into Git-tracked test directories (such as `server/test/`).
9. **Reverse Dependency**: Referencing private route implementations (`server/agents/routes/*`) in underlying helper classes or common utilities.
10. **Concurrency Hazards**: Running long-running physical tasks without concurrency write locks, or omitting `clientId` verification on stream reconnects.

## 8. Regression Testing & Temp File Protection
When making changes involving chat streams, agent collaboration, or tool integrations, verify all relevant tests and adhere strictly to temporary output rules:

### 8.1 Temp File Sandbox Rules (Critical)
- All temporary cache, index, graph, and serialization output generated by tests, debugging, or validation scripts **must be written to `/.tmp/` at the project root**.
- Writing temporary test outputs directly to `server/test/` is strictly prohibited to keep the Git repository clean.

### 8.2 Recommended Regression Test Commands
- **Backend Tests**:
  ```bash
  cd server
  pytest test/test_chat_stream_events.py test/test_chat_history_segments.py test/test_tool_event_ui_metadata.py test/test_director_graph.py test/test_director_handoff_protocol.py test/test_director_skip_confirmation.py test/test_stream_semantics_runtime.py
  ```
- **Frontend Tests**:
  ```bash
  cd client
  npm run test -- src/components/stores/__tests__/chatStore.spec.ts src/utils/__tests__/streamingRuntime.spec.ts
  ```

## 9. AI Agent Permission & Safety Rules
1. Unless explicitly requested by the user in **Simplified Chinese**, the AI assistant is only permitted to use read-only Git commands. Executing `git commit`, `git push`, or other write operations is strictly prohibited.
2. Even if auto-approval policies are active, the AI assistant must prioritize security, never treat auto-approval as user intent, and strictly avoid operating remote repositories with GitHub CLI or similar tools.
