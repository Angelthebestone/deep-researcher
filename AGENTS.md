# AGENTS.md

This repository builds a technology surveillance system. Start with [spec.md](spec.md), [.vscode/rules.md](.vscode/rules.md), and [README.md](README.md). Use [plan-techSurveillanceSystem.md](plan-techSurveillanceSystem.md) for roadmap context, but do not duplicate it here.

## Working Rules

- Treat [src/vigilador_tecnologico/contracts/models.py](src/vigilador_tecnologico/contracts/models.py) and [schemas/](schemas/) as the source of truth for data shapes.
- Keep environment and secret access inside [src/vigilador_tecnologico/integrations/credentials.py](src/vigilador_tecnologico/integrations/credentials.py).
- Route provider-specific calls through [src/vigilador_tecnologico/integrations/](src/vigilador_tecnologico/integrations/); services and workers should not hardcode SDK details or provider URLs.
- Keep service outputs deterministic unless a model-backed path is explicitly documented.
- Use LangGraph for research orchestration and FastAPI SSE for long-running progress.
- Preserve document IDs, idempotency keys, and operation history across ingest, extraction, research, scoring, and reporting.
- When a change adds or alters an event, endpoint, artifact, or contract field, update [spec.md](spec.md) and the affected schema files in the same change.
- Prefer small, readable edits over abstractions. Check the implementation before assuming a future phase already exists.

## Validation

- Install dependencies with `pip install -e .`.
- Use `python -m unittest tests.test_live_e2e` for the end-to-end smoke path.
- Use `python -m unittest tests.test_sse_stream` to validate SSE progress.
- Use `python -m unittest tests.test_mistral_adapter` to validate the Mistral fallback path.

## Current Gaps To Track

- Research and scoring still need to preserve breadth/depth, visited URLs, summarized learnings, market alternatives, version gaps, source URLs, risk severity, and the Groq -> Mistral fallback history in the operation trail.
- Reporting still needs a persisted, retrievable final artifact, a read/download endpoint, and a minimal dashboard that shows SSE progress, operation state, and the final report.
- Operations still need notification-service plus basic health/readiness/logging/metrics before any final split into gateway, workers, and broker manifests.
- Keep any future work in those areas aligned with [spec.md](spec.md) and the affected JSON Schemas.