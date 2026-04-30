# Copilot Instructions for Vigilador Tecnologico

A technology surveillance system that analyzes documents, extracts technologies, normalizes them, and compares against market state using multi-agent orchestration.

## Quick Reference

**Key files to read first:**
- [spec.md](../spec.md) — Implementation specification (source of truth)
- [.vscode/rules.md](../.vscode/rules.md) — Detailed guardrails and patterns
- [AGENTS.md](../AGENTS.md) — High-level working rules

## Build, Test, and Run

### Backend (Python 3.13)

**Setup:**
```bash
pip install -e .
```

**Run locally (no reload to avoid Windows duplicates):**
```bash
.\.venv\Scripts\python.exe -m uvicorn vigilador_tecnologico.api.main:app --host 0.0.0.0 --port 8000
```

**Run all tests:**
```bash
.\.venv\Scripts\python.exe -m unittest discover tests
```

**Run specific test suites:**
- End-to-end smoke test: `python -m unittest tests.test_live_e2e`
- SSE streaming validation: `python -m unittest tests.test_sse_stream`
- Mistral adapter/fallback: `python -m unittest tests.test_mistral_adapter`
- Operational endpoints: `python -m unittest tests.test_operational_endpoints`
- Document analysis: `python -m unittest tests.test_document_analyze`
- Prompt engineering: `python -m unittest tests.test_prompt_engineering`

### Frontend (Next.js 14, Node.js)

**Setup:**
```bash
cd frontend
npm install
```

**Run dev server:**
```bash
npm run dev -- --port 3001 --hostname 127.0.0.1
```

**Build and run production:**
```bash
npm run build
npm start
```

**Lint:**
```bash
npm run lint
```

### Full Local Startup

**Windows (all-in-one):**
```bash
start_all.bat
```
Backend runs on `127.0.0.1:8000`, frontend on `127.0.0.1:3001`.

**Docker:**
```bash
docker compose up --build
```

## High-Level Architecture

The system flows: **Upload → Parse → Extract → Normalize → Research (Deep) → Score → Report**

### Core Layers

| Layer | Tech | Responsibility |
|-------|------|-----------------|
| **API Gateway** | FastAPI + SSE | HTTP endpoints, upload, streaming progress |
| **Services** | Python modules | Business logic (extraction, research, scoring, reporting) |
| **Orchestration** | LangGraph | Research state machine with breadth/depth budgets |
| **Integrations** | Python adapters | Multi-provider model calls (Gemini, Groq, Mistral) |
| **Storage** | Disk-based (`.vigilador_data/`) | Documents, parsed text, mentions, reports, audit logs |
| **Frontend** | Next.js + React + Tailwind | Dashboard for upload, SSE progress, graph, final report |

### Model Stack

- **Ingestion:** Gemini Robotics ER 1.6 → ER 1.5 → Gemma 4 26B (fallback chain)
- **Reasoning/Planning:** Gemma 4 31B
- **Normalization:** Gemma 4 26B
- **Web Research (Serial Branches):**
  - Branch 1: `Gemini 3.1 Flash Lite` (search) → `Gemma 4 26B` (review)
  - Branch 2: `Mistral Small 4` (search) → `Mistral Large Latest` (review)
- **Synthesis:** Gemini 3 Flash
- **Embeddings:** Gemini Embedding 2

All fallbacks are explicit: if a model fails, the system degrades deterministically and marks `fallback_reason` in SSE events.

### Request Flow

1. **Document Upload:** `POST /api/v1/documents/upload` → stored with stable `document_id`
2. **Parsing:** OCR/extraction with Gemini Robotics or fallback
3. **Extraction:** Identify technology mentions → persist as `TechnologyMention`
4. **Analysis:** `POST /api/v1/documents/{document_id}/analyze` + `idempotency_key`
5. **SSE Stream:** `GET /api/v1/documents/{document_id}/analyze/stream` emits real-time events
6. **Research:** LangGraph orchestrates web search + review across both branches
7. **Scoring:** Compare technologies against market, assess risks
8. **Reporting:** Synthesis into markdown report + JSON artifact
9. **Frontend:** React dashboard hydrates from SSE events and fetches final report

## Key Conventions

### Source of Truth

- **Data Contracts:** `src/vigilador_tecnologico/contracts/models.py` + `schemas/*.json`
  - Services must normalize all external payloads into model types before returning
  - Frontend types in `frontend/src/types/contracts.ts` must mirror backend
  - If you change a contract, update `spec.md` and schema files in the same change

- **Specification:** `spec.md` is the spec. Never generate code that contradicts it.

### Boundaries

| Boundary | Rule |
|----------|------|
| **Credentials** | Only `src/vigilador_tecnologico/integrations/credentials.py` reads env/`.env`. Other modules use exported getters. |
| **Adapters** | All provider calls go through `src/vigilador_tecnologico/integrations/` (GeminiAdapter, GroqAdapter, MistralAdapter). Services/workers never hardcode URLs, keys, or SDK details. |
| **Services** | Must return normalized contract types, not raw provider payloads. Use `*_with_context` API. |
| **Orchestration** | LangGraph only. No manual loops or recursion for research state management. |

### Pipeline Patterns

- **Stage Context:** Always use `build_stage_context()` from `services/_stage_context.py` for events. Never construct dicts manually.
- **SSE Routing:** Keep `api/sse_routes.py` for routing, `api/_sse_formatters.py` for formatting, `api/_research_operations.py` for state.
- **Determinism:** Service outputs must be deterministic for the same input unless explicitly model-backed and documented.
- **Fallbacks:** Explicit only. If a model fails, degrade deterministically and surface `fallback_reason` in `stage_context` and SSE details.
- **Prompts:** Use lightweight models (Flash Lite) to extract learnings before passing to core reasoner. No full HTML in core prompts.
- **JSON Validation:** Never treat model output as valid until it passes explicit parsing and shape checks.

### Frontend Integration

- Frontend consumes events via `GET /api/v1/documents/{document_id}/analyze/stream`
- Deduplicates events by `event_id` to avoid double-rendering
- Restores UI state from Supabase snapshots (or localStorage fallback)
- Uses stable `document_id` for document analysis, synthetic `document_id` for chat research
- CSS is centralized in `frontend/src/app/globals.css`; ensure components live under `frontend/src/` for Tailwind visibility

### Idempotency

- **Document Analysis:** `idempotency_key` is derived from document for deterministic result
- **Chat/Research:** `idempotency_key` is generated by frontend per attempt; reuse only to resume exact operation
- Never derive chat key solely from raw query; frontend must generate stable key per attempt

## Testing Strategy

- **Unit tests:** Live in `tests/` parallel to `src/`
- **Integration tests:** Test end-to-end flows (e.g., `test_live_e2e`, `test_sse_stream`)
- **Adapter tests:** Validate fallback chains (e.g., `test_mistral_adapter`)
- **Schema tests:** `test_schema_contract_alignment` ensures models.py and schemas/*.json stay in sync

## Common Tasks

### Adding a New Endpoint

1. Define request/response in `contracts/models.py`
2. Implement business logic in a `service.py` file (import adapters from `integrations/`)
3. Add route in `api/` (use `build_stage_context` for events)
4. Update `spec.md` with the new endpoint signature
5. Add test in `tests/test_*.py`

### Adding a New Service Integration

1. Create adapter in `src/vigilador_tecnologico/integrations/` (e.g., `new_provider.py`)
2. Import credentials from `credentials.py`
3. Return normalized `models.py` types, not raw payloads
4. Update `spec.md` if this changes model stack or fallback chain

### Modifying Contracts

1. Update `src/vigilador_tecnologico/contracts/models.py`
2. Update `schemas/*.json` (JSON Schema)
3. Update `frontend/src/types/contracts.ts` if frontend is affected
4. Update `spec.md` with the change
5. Run `python -m unittest tests.test_schema_contract_alignment`

### Debugging Research Flow

- Check `api/_research_operations.py` for operation state
- Monitor SSE events: sequence, `event_id`, `stage_context`, `failed_stage`, `fallback_reason`
- Look at LangGraph nodes in `workers/research.py` and `pipeline/nodes.py`
- Ensure `planificador_node` consumes the refined query, not raw target

### Windows-Specific Notes

- Always use `.venv\Scripts\python.exe` (not global `python`)
- Backend runs without `--reload` (use `start_all.bat` to restart)
- Use backslashes in paths or glob patterns
- `stop_all.bat` equivalent: kill processes on ports 8000, 3001 or use Task Manager

## Related Instruction Files

- **Frontend styling:** [.github/instructions/frontend-styling.instructions.md](.github/instructions/frontend-styling.instructions.md)
- **Implementation guardrails:** Skills in `.github/skills/` and `.vscode/rules.md`
- **Project-specific rules:** [AGENTS.md](../AGENTS.md) for high-level, [.vscode/rules.md](../.vscode/rules.md) for detailed

## Quick Troubleshooting

| Issue | Check |
|-------|-------|
| Port 8000/3001 already in use | Kill via `netstat -ano`, PowerShell `Stop-Process -Id`, or `start_all.bat` script |
| Tests fail with import errors | Ensure `.venv/Scripts/python.exe` and `pip install -e .` completed |
| Frontend CSS not applying | Verify component is in `frontend/src/`, component wrapper is inside App Router, Tailwind globs in `tailwind.config.ts` |
| SSE events drop or duplicate | Check `event_id` deduplication in frontend `AnalysisStream.tsx`, verify `sequence` is monotonic in backend |
| Research hangs or stalls | Check `_ensure_research_operation()` does not reuse terminal operations; ensure `ResearchWorker` is not waiting on concurrent model calls |
| Fallback not surfaced in UI | Verify `fallback_reason` is in `stage_context` and SSE event `details` |

## Environment Variables

**Backend (.env or shell):**
- `GEMINI_API_KEY` — Google Gemini/Robotics
- `GROQ_API_KEY` — Groq (research fallback)
- `MISTRAL_API_KEY` — Mistral (web search branch 2)

**Frontend (.env.local):**
- `NEXT_PUBLIC_API_BASE_URL` — API endpoint (defaults to `http://127.0.0.1:8000`)
- `NEXT_PUBLIC_SUPABASE_URL` — Supabase project URL (optional)
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Supabase anon key (optional)

See `.env.example` for template.
