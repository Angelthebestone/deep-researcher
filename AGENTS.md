# AGENTS.md

Technology surveillance system. See [spec.md](spec.md) for full specification, [.vscode/rules.md](.vscode/rules.md) for implementation guardrails.

## Quick Start

```bash
# Backend (Python 3.13, .venv)
pip install -e .
start_all.bat                # Launches backend :8000 + frontend :3001

# Backend without script (no --reload on Windows to avoid duplicate processes)
.venv\Scripts\python.exe -m uvicorn vigilador_tecnologico.api.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend && npm install && npm run dev -- --port 3001 --hostname 127.0.0.1

# Docker
docker compose up --build
```

Always use `.venv\Scripts\python.exe` — never the global Python on Windows.

## Testing

```bash
# CI regression suite (matches .github/workflows/ci.yml)
.venv\Scripts\python.exe -m unittest tests.test_document_upload tests.test_document_analyze tests.test_document_analyze_stream tests.test_schema_contract_alignment tests.test_sse_stream tests.test_research_fallback tests.test_normalization_reporting tests.test_ingestion_persistence -v

# Individual suites
.venv\Scripts\python.exe -m unittest tests.test_live_e2e
.venv\Scripts\python.exe -m unittest tests.test_sse_stream
.venv\Scripts\python.exe -m unittest tests.test_mistral_adapter
.venv\Scripts\python.exe -m unittest tests.test_operational_endpoints tests.test_document_analyze

# Frontend
cd frontend && npm run lint && npm run build
```

## Architecture

**Pipeline:** Upload → Parse → Extract → Normalize → Research (LangGraph) → Score → Report

**Backend** (`src/vigilador_tecnologico/`):
- `api/` — FastAPI HTTP entry, SSE routes. Routing in `sse_routes.py`, formatting in `_sse_formatters.py`, research state in `_research_operations.py`, DI via `AppDependencies` in `documents.py`
- `contracts/models.py` — source of truth for all data shapes
- `integrations/` — adapters (GeminiAdapter, GroqAdapter, MistralAdapter); `credentials.py` is the ONLY module that reads env/`.env`
- `services/` — business logic; use `build_stage_context()` from `_stage_context.py` for all events, `*_with_context` API for orchestrator calls
- `pipeline/` — LangGraph orchestration; nodes are thin wrappers, LLM logic lives in services
- `workers/` — background executors (analysis, research)
- `storage/` — disk-based repos under `.vigilador_data/`

**Frontend** (`frontend/`): Next.js 14 App Router, React 18, Tailwind, HeroUI (NextUI v2), Zustand. Port 3001. See [frontend-styling.instructions.md](.github/instructions/frontend-styling.instructions.md).
- **State management**: Zustand via `frontend/src/stores/appStore.ts`.
- **UI Library**: HeroUI (NextUI v2) — all custom UI primitives in `components/ui/` were removed and replaced by HeroUI equivalents.
- **Component structure**:
  - `components/layout/` — AppShell, ViewToggle
  - `components/chat/` — ChatView, ChatInputBar, MessageBubble, ThinkingTimeline
  - `components/research/` — ResearchConsole
  - `components/graph/` — GraphView
- **Navigation**: Dual-view system (Chat | Graph) via floating toggle; DashboardWorkspace removed.
- **Styling**: "Zen-Data" aesthetic — minimal, non-boxy, white/smoke background with purple and lime accents.
- **Dependencies added**: `zustand`, `react-markdown`, `remark-gfm`.
- **Build verification**: `npm run build` passes successfully.

**JSON Schemas** (`schemas/*.schema.json`) — contract truth alongside `contracts/models.py`.

## Boundaries (enforced)

| Boundary | Rule |
|----------|------|
| Credentials | Only `integrations/credentials.py` reads env/`.env` |
| Adapters | All provider calls through `integrations/` — no hardcoded SDK details in services |
| Contracts | Services normalize to `contracts/models.py` types before returning |
| Determinism | Outputs deterministic unless explicitly model-backed and documented |
| Spec sync | Changing behavior/contracts → update `spec.md` and affected schemas in the same commit |

## Key Rules (non-obvious)

- **No comments** in code unless explicitly requested.
- **LangGraph only** for research state — no manual loops or recursion.
- **Terminal operations are not reusable** — `find_by_idempotency_key()` must return `None` for completed/failed ops.
- **Chat SSE emits the same envelope** as `analyze/stream`. Terminal failures always use `AnalysisFailed`.
- **`report_markdown`** for research output; **`report_artifact`** for document reports — never overload a single `report` field.
- **`build_stage_context()`** required for all SSE events — no manual context dicts.
- **Prompt engineering** is tool-free and deterministic; `fallback_reason` must surface when model degrades.
- **Chat flow order**: `PromptImprovementStarted → PromptImproved → ResearchRequested → ResearchPlanCreated`. Never emit `ResearchRequested` before `PromptImproved`.
- **Idempotency**: document analysis derives key from document; chat generates per-attempt key from frontend.
- **Frontend deduplicates** SSE by `event_id` and hydrates from Supabase (`localStorage` fallback). Don't re-open `EventSource` on re-render.

## Environment Variables

**Backend** (`.env`):
- `GEMINI_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`

**Frontend** (`frontend/.env.local`):
- `NEXT_PUBLIC_API_BASE_URL` — defaults to `http://127.0.0.1:8000`
- `BACKEND_API_BASE_URL` — internal rewrite target, defaults to `http://127.0.0.1:8000`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY` — optional snapshot persistence

## Ports

- Backend: `8000`
- Frontend: `3001` (not 3000 — `start_all.ps1` uses 3001)

## Local Skills

Repo-local skills live in `.agents/skills/` and load via the `skill` tool:

| Skill | Trigger / Use |
|-------|---------------|
| **karpathy-guidelines** | Coding best practices, avoid LLM pitfalls, complex implementations |
| **caveman** | Ultra-compressed communication (`/caveman`) |
| **cavecrew** | Delegate to subagents (`/cavecrew`) |
| **caveman-commit** | Compressed commit messages |
| **caveman-review** | Compressed PR reviews |

## MCP Servers (opencode)

Configured in `~/.config/opencode/opencode.jsonc`. Use these tools in prompts:

| MCP | Usage | Prompt keyword |
|-----|-------|----------------|
| **vercel** | Deployments, logs, env vars, docs search | `use vercel` |
| **lucide** | Search Lucide icons by name, get JSX/SVG | `use lucide` |
| **context7** | Library docs (Shadcn/UI, Tailwind, HeroUI, etc.) | `use context7` |
| **fetch** | Fetch any URL as markdown/HTML/text | `use fetch` |
| **github** | Repositories, issues, PRs, commits, search | `use github` |
| **upstash** | Redis, QStash, Workflow, Box management | `use upstash` |
| **sequential-thinking** | Reflective problem-solving and planning | `use sequential-thinking` |

**Vercel MCP**: Remote at `https://mcp.vercel.com` with OAuth. First use opens browser for login.

**Context7 MCP**: Remote at `https://mcp.context7.com/mcp`. Free, no API key. Use for component examples, API refs, theming docs.

**Lucide MCP**: Local via `npx -y lucide-icons-mcp`. Search icons and get import paths for `lucide-react`.

**Fetch MCP**: Local via `npx -y mcp-fetch-server`. Generic URL fetching for arbitrary documentation.

**GitHub MCP**: Local via `github-mcp-server.exe`. Requires `GITHUB_PERSONAL_ACCESS_TOKEN` env var.

**Upstash MCP**: Local via `npx -y @upstash/mcp-server@latest`. Manages Redis databases, QStash queues/schedules, Workflow runs, and Box containers.

**Sequential Thinking MCP**: Local via `npx -y @modelcontextprotocol/server-sequential-thinking`. Use for complex multi-step reasoning, planning, and problem decomposition.

Example: When building UI components, add `use context7` to get Shadcn/UI docs, `use lucide` to find icons, or `use github` to manage PRs and issues.