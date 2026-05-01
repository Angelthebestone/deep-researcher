# Project Rules

- **No comments**: Avoid unnecessary comments.
- **No repetitive code**: Do not repeat logic or large blocks of code.
- **Avoid DRY dogma**: Avoid over-engineering or complex abstractions in the name of DRY. Prefer readability and simplicity.
- **Spec First**: Before implementing any feature, read `spec.md`. Never generate code that contradicts the specefications. Tests are generated from the Validación section. Never written manually.
- **Credential boundary**: Only `src/vigilador_tecnologico/integrations/credentials.py` may read environment variables or load `.env`. Other modules must use the exported getters.
- **Adapter boundary**: External model calls must go through the adapters in `src/vigilador_tecnologico/integrations`. Services and workers must not hardcode provider URLs, keys, or SDK-specific request shaping.
- **Contract boundary**: Services must normalize external payloads into `src/vigilador_tecnologico/contracts/models.py` types before returning them.
- **Deterministic core**: Keep service outputs deterministic for the same input unless the behavior is explicitly model-backed and documented.
- **Spec and schema sync**: If a change alters behavior, contracts, validation assumptions, or shape of model outputs, update `spec.md` and any affected schema files in the same change.
- **Dependency discipline**: Prefer stdlib and existing project modules first. Add new dependencies only when the current implementation cannot remain simple and maintainable without them.
- **No God Prompts**: During Web Extraction, do not load full HTML into the core reasoner. Extract minimal 'Learnings' using a lightweight tasker model (e.g., Flash Lite) before passing context to the next state.
- **Streaming First**: Long-running operations (like Deep Research) must emit partial progress via Server-Sent Events (SSE) to prevent UX freezing.
- **Shared Stage Context**: Use `src/vigilador_tecnologico/services/_stage_context.py:build_stage_context` for all pipeline events. Never construct context dictionaries manually.
- **Research Worker Composition**: Keep `ResearchWorker` as orchestration-only. Web search logic belongs in `services/web_search.py` and review/analysis logic belongs in `services/research_analysis.py`.
- **SSE Routing Split**: Keep `api/sse_routes.py` focused on routing and stream orchestration. Put payload formatting in `api/_sse_formatters.py` and research operation state logic in `api/_research_operations.py`.
- **Documents API DI**: Do not add new global mutable singletons in `api/documents.py`. Runtime collaborators must be grouped in the `AppDependencies` container and guarded with `asyncio.Lock` for launch coordination.
- **Chat SSE Contract**: `chat/stream` must emit the same base SSE envelope as `analyze/stream`; do not send ad hoc prompt-engineering events without `event_id`, `sequence`, `operation_id`, `operation_type`, `operation_status`, `document_id`, `idempotency_key`, `details`, and `stage_context`.
- **Canonical Research Identity**: Build one canonical research request before executing research. Once `document_id`, `idempotency_key`, `target_technology`, `breadth`, and `depth` are fixed, prompt refinement may only improve `query`, not mutate research identity.
- **No Early ResearchRequested In Chat**: `chat/stream` must not emit or persist `ResearchRequested` before `PromptImproved` completes. The conversational handoff order is `PromptImprovementStarted -> PromptImproved -> ResearchRequested -> ResearchPlanCreated`.
- **Chat Retry Identity**: Do not derive chat `idempotency_key` values solely from the raw query. The frontend must generate a per-attempt key for `chat/stream` and only reuse it when resuming that exact operation.
- **JSON Validation First**: Never treat model output as valid JSON unless it passes explicit parsing and shape checks. If the output includes prompt echo, explanatory prose, or partial JSON, fall back to deterministic logic.
- **Explicit Prompt Fallbacks Only**: If `PromptEngineeringService` degrades to a deterministic pass-through brief, it must surface `fallback_reason` in `stage_context` and SSE details. Do not let prompt fallback masquerade as a successful model-authored refinement.
- **Tool-Free Prompt Refinement**: Prompt-engineering stages must not attach web search tools; keep them deterministic and tool-free so the refinement step cannot pollute the query shape.
- **Journal Sequencing**: Operation events must persist a monotonic `sequence`. Do not fingerprint payloads to derive event identity; use an explicit `event_key` only when deduplicating the same logical transition.
- **Split SSE Reports**: Do not overload `report` with different shapes. Use `report_markdown` for research output and `report_artifact` for persisted document reports.
- **No Introspection**: Avoid `getattr` or `hasattr` to discover service capabilities in `orchestrator.py`. Rely on explicit interfaces and `*_with_context` methods.
- **Document the guardrails**: When a failure pattern is discovered during implementation, add the corresponding "do not do this" rule to `.vscode/rules.md` in the same change instead of keeping it as implicit memory.
- **Terminal Operations Not Reusable**: Never reuse operations that have reached terminal status (failed or completed) in `find_by_idempotency_key()`. Return None and let a new operation be created. Returning a terminal operation to `_ensure_research_operation()` causes `research_event_stream` to poll a dead operation indefinitely, creating stagnation.
- **Sequential Research Execution**: Research branches must execute serially. Never call multiple model providers concurrently within the research pipeline.
- **Zen-Data Frontend**: Frontend components must maintain the minimal, non-boxy aesthetic. Avoid heavy borders, excessive shadows, and card-based layouts. Use whitespace, subtle backdrop-blur, and floating elements instead.

## Coding Practices to Avoid (Guardrails)

- **Manual Context Dicts**: Do not use `stage_context = {"stage": "...", ...}`. Use `build_stage_context`.
- **Service Introspection**: Do not use reflection to call service methods; use the standardized `_with_context` API.
- **Model Profile Leakage**: Do not import `model_profiles.py` in the pipeline layer; keep it restricted to services and integrations.
- **Mutable Research Identity**: Do not let prompt-engineering rewrite the canonical `target_technology`, `breadth`, `depth`, or `idempotency_key` after the research operation already exists.
- **Shared Failure Event**: Do not invent a second terminal failure event for research streams. `chat/stream`, `research/stream`, and `analyze/stream` must all surface terminal failures as `AnalysisFailed` so the dashboard has one failure contract.
- **Ambiguous SSE Report Fields**: Do not emit `report` in SSE payloads if the underlying shape can differ between research and document analysis.
- **Deterministic SSR Text**: Do not format timestamps or other hydration-sensitive text with locale-dependent defaults in server-rendered UI; use a stable formatter or a fixed locale so server and client render the same content.
