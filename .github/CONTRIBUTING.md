# Contributing to SparkArc

SparkArc is not a small demo repository. It is a multi-agent creative platform with long-lived architectural constraints, dual streaming protocols, and a fairly opinionated integration model. Please read this guide before opening a pull request.

## Before you change code

Start here:

- [AGENTS.md](../AGENTS.md) for project-wide implementation rules
- [docs/architecture.md](../docs/architecture.md) for the runtime and agent model
- [docs/database-migration.md](../docs/database-migration.md) if you plan to touch persistence

The most important rule is simple: **extend existing integration points instead of creating parallel pipelines**.

## Architecture rules that matter in review

SparkArc has two primary streaming paths. Do not mix them:

- **Chat pipeline (NDJSON)**: frontend entry is `client/src/components/stores/chatStore.ts`; backend entry is `server/agents/routes/chat.py`
- **Business streaming pipeline (SSE / semantic frames)**: frontend entry is `client/src/utils/streamingRuntime.ts`; backend bridge is `server/agents/routes/streaming_utils.py`

Common review failures in this repository:

- Duplicating stream readers or loading state machines in page components
- Bypassing the agent tool facade in `server/agents/agent_tools.py`
- Writing ad hoc text replacement logic instead of reusing `server/agents/tools/common.py::_apply_patch`
- Re-implementing token or semantic chunking instead of reusing the existing chunking infrastructure
- Adding runtime temp output to tracked test directories instead of `/.tmp/`
- Editing migrations manually instead of changing models and generating migrations through the project flow

## If you add or change an agent

Please verify all of the following:

1. Reuse the existing bases (`SparkBaseAgent` and `SparkAgentExecutor`)
2. Register metadata and routing touchpoints instead of adding hidden entry paths
3. Keep the three prompt modalities aligned:
   - `system`
   - `chat_system`
   - `pipeline_system`
4. Route new tools through the shared tool registry and facade
5. Update frontend mappings when the agent affects UI identity or routing
6. Add or update regression tests for the affected execution path

The project-specific rules for prompt modality, tool references, and registration are defined in [AGENTS.md](../AGENTS.md). Reviewers will treat those rules as authoritative.

## If you change frontend behavior

Please keep these repository conventions intact:

- User-visible strings must go through Vue I18n
- Long-running flows should use `createStreamingTask`
- Chat stream consumption must stay inside `chatStore`
- Tool event UI linkage should continue to rely on backend-provided metadata

When UI behavior changes, include screenshots or short recordings in the pull request if the change is not obvious from code review alone.

## If you change backend or persistence behavior

- Do not scatter business logic into route handlers
- Reuse existing service/factory layers before introducing new ones
- If a schema change is required, update `server/core/models.py` first and follow the project migration workflow
- Do not hand-edit generated migration files

## Testing expectations

At minimum, run the checks that match your change surface.

Frontend:

```bash
cd client
npm run i18n:check:strict
npm run typecheck
npm run test
```

Backend:

```bash
cd server
python -m pytest -vv -s test/
```

If your change affects build or packaging behavior, also run the corresponding build command locally when practical.

## Pull request expectations

Good SparkArc pull requests usually include:

- A short explanation of the user or maintainer problem being solved
- The architectural touchpoints involved
- Notes about protocol boundaries, registry updates, or migration impact when relevant
- The exact tests you ran
- Screenshots, logs, or reproduction notes when they materially help review

Please keep temporary validation artifacts out of tracked directories. Use `/.tmp/` for generated debugging output.

## Security and disclosure

If you found a security issue, do **not** open a public bug report with exploit details. Follow [SECURITY.md](SECURITY.md) instead.

## License and branding reminder

SparkArc is licensed under AGPL-3.0-only unless a subcomponent explicitly states otherwise. The project name, logo, and brand identity are not automatically granted for third-party white-label use. Review the repository license and legal notes before proposing redistribution or operator-facing changes.
