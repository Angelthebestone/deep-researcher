from __future__ import annotations

import asyncio
import json
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from vigilador_tecnologico.api import sse_routes
from vigilador_tecnologico.storage.operations import OperationJournal


REAL_ASYNCIO_SLEEP = asyncio.sleep


async def _noop_sleep(*args, **kwargs):
    return await REAL_ASYNCIO_SLEEP(0)


def _parse_sse_chunk(chunk: str | bytes) -> dict[str, object]:
    if isinstance(chunk, bytes):
        chunk = chunk.decode("utf-8")
    return json.loads(chunk.removeprefix("data: ").strip())


class _PromptJournalStub:
    _events: list[dict] = []
    
    def __init__(self):
        self._events = []
    
    def record_event(self, *args, **kwargs):
        event = {
            "event_id": "stub-event-id",
            "operation_id": args[0] if args else "unknown",
            "operation_type": "research",
            "status": "running",
            "operation_status": "running",
            "details": kwargs.get("details") or {},
            "message": kwargs.get("message") or "",
        }
        self._events.append(event)
        return event

    def mark_running(self, operation_id, *, message=None, details=None, event_key=None):
        event = {
            "event_id": f"event-{len(self._events)}",
            "operation_id": operation_id,
            "operation_type": "research",
            "status": "running",
            "operation_status": "running",
            "details": details or {},
            "message": message or "",
        }
        self._events.append(event)
        return event

    def mark_failed(self, *args, **kwargs):
        return None
    
    def list_events(self, operation_id):
        return self._events
    
    def load(self, operation_id):
        return {"status": "running"}


class _FakeResearchService:
    async def execute_full_research(self, target_technology, query, breadth, depth, freshness, max_sources, progress_callback):
        from dataclasses import dataclass
        
        @dataclass
        class FakeResearchExecutionResult:
            plan: dict
            branch_results: list
            report: str
            stage_context: dict
        
        progress_callback("ResearchPlanCreated", {
            "stage": "ResearchPlanCreated",
            "model": "gemma-4-31b-it",
            "breadth": breadth,
            "depth": depth,
        })
        
        progress_callback("ResearchNodeEvaluated", {
            "stage": "ResearchNodeEvaluated",
            "model": "gemma-4-26b-it",
            "branch_id": "gemini-grounded",
        })
        
        # No enviar ResearchCompleted via callback - lo maneja execute_research_operation
        
        return FakeResearchExecutionResult(
            plan={"plan_id": "plan-1", "branches": []},
            branch_results=[{
                "branch_id": "gemini-grounded",
                "provider": "gemini_grounded",
                "executed_queries": ["plasma gasification biomass"],
                "learnings": ["Plasma gasification has active research."],
                "source_urls": ["https://example.com/research"],
                "iterations": 1,
                "embeddings": [],
            }],
            report="# Report\n\nResearch completed.",
            stage_context={
                "stage": "ResearchCompleted",
                "model": "gemini-3-flash-preview",
            },
        )


class SSEStreamIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = Path.cwd() / ".codex-test-tmp" / f"sse-{uuid4().hex}"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.operation_journal = OperationJournal(base_dir=self.temp_dir)

    async def test_chat_stream_emits_prompt_then_research_requested(self):
        async def _fake_improve_query(query: str):
            return {
                "refined_query": "Deep technical and market research on plasma gasification for biomass",
                "target_technology": "Gasificación por plasma para biomasa",
                "suggested_breadth": 3,
                "suggested_depth": 2,
                "keywords": ["plasma gasification", "biomass syngas"],
            }

        captured: dict[str, object] = {}

        def _fake_ensure_operation(request, *, start_requested=True):
            captured["start_requested"] = start_requested
            operation = {
                "operation_id": "chat-op-1",
                "operation_type": "research",
                "subject_id": request["document_id"],
                "status": "running",
                "idempotency_key": request["idempotency_key"],
            }
            return operation, False

        async def _fake_research_event_stream(request, *, custom_query=None, **kwargs):
            captured["custom_query"] = custom_query
            payload = {
                "event_id": "research-event-1",
                "sequence": 3,
                "operation_id": "chat-op-1",
                "operation_type": "research",
                "operation_status": "running",
                "event_type": "ResearchRequested",
                "message": "ResearchRequested",
                "document_id": request["document_id"],
                "idempotency_key": request["idempotency_key"],
                "details": {
                    "stage_context": {
                        "stage": "ResearchRequested",
                        "model": "serial-coordinator",
                        "breadth": request["breadth"],
                        "depth": request["depth"],
                    }
                },
                "stage_context": {
                    "stage": "ResearchRequested",
                    "model": "serial-coordinator",
                    "breadth": request["breadth"],
                    "depth": request["depth"],
                },
            }
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        class _FakePromptEngineeringService:
            def __init__(self, model="fake"):
                self.model = model

            async def improve_query(self, raw_query):
                return await _fake_improve_query(raw_query)

        with (
            patch.object(sse_routes, "PromptEngineeringService", new=_FakePromptEngineeringService),
            patch.object(sse_routes, "_ensure_research_operation", new=_fake_ensure_operation),
            patch.object(sse_routes, "research_event_stream", new=_fake_research_event_stream),
            patch.object(sse_routes, "operation_journal", new=_PromptJournalStub()),
        ):
            response = await sse_routes.stream_chat_research(
                "investiga sobre Gasificación por plasma para biomasa",
                breadth=3,
                depth=2,
                freshness="past_year",
                max_sources=10,
                idempotency_key="chat-plasma-1",
            )
            payloads = []
            async for chunk in response.body_iterator:
                payloads.append(_parse_sse_chunk(chunk))

        self.assertEqual(captured["start_requested"], False)
        self.assertEqual(
            [payload["event_type"] for payload in payloads],
            ["PromptImprovementStarted", "PromptImproved", "ResearchRequested"],
        )
        self.assertEqual(captured["custom_query"], "Deep technical and market research on plasma gasification for biomass")
        self.assertEqual([payload["sequence"] for payload in payloads], [1, 2, 3])
        self.assertEqual(payloads[0]["stage_context"]["stage"], "PromptImprovementStarted")
        self.assertEqual(payloads[1]["stage_context"]["stage"], "PromptImproved")
        self.assertEqual(payloads[2]["stage_context"]["stage"], "ResearchRequested")

    async def test_research_stream_emits_requested_then_planner_then_node_evaluation_then_completed(self):
        request = sse_routes._build_research_request(
            "Analyze Plasma Gasification for Biomass",
            breadth=3,
            depth=2,
            freshness="past_year",
            max_sources=10,
            idempotency_key="research-plasma-1",
        )
        fake_research_service = _FakeResearchService()
        with (
            patch.object(sse_routes, "research_service", new=fake_research_service),
            patch.object(sse_routes, "operation_journal", new=self.operation_journal),
            patch.object(sse_routes.asyncio, "sleep", _noop_sleep),
        ):
            payloads = []
            async for chunk in sse_routes.research_event_stream(request):
                payloads.append(_parse_sse_chunk(chunk))

        self.assertEqual(
            [payload["event_type"] for payload in payloads],
            ["ResearchRequested", "ResearchPlanCreated", "ResearchNodeEvaluated", "ReportGenerated", "ResearchCompleted"],
        )
        self.assertEqual([payload["sequence"] for payload in payloads], [1, 2, 3, 4, 5])
        self.assertEqual(payloads[1]["details"]["model"], "gemma-4-31b-it")
        self.assertEqual(payloads[2]["details"]["model"], "gemma-4-26b-it")
        self.assertEqual(payloads[-1]["details"]["stage"], "ResearchCompleted")
        self.assertEqual(payloads[-1]["details"]["model"], "gemini-3-flash-preview")
        self.assertTrue(str(payloads[-2]["report"]).startswith("# Report"))

    def test_build_research_request_normalizes_spanish_query(self):
        request = sse_routes._build_research_request(
            "investiga sobre Gasificación por plasma para biomasa.",
            breadth=3,
            depth=2,
            freshness="past_year",
            max_sources=10,
            idempotency_key="chat-plasma-2",
        )

        self.assertEqual(request["target_technology"], "Gasificación por plasma para biomasa")
        self.assertEqual(request["document_id"], "research-gasificaci-n-por-plasma-para-biomasa")
        self.assertEqual(request["idempotency_key"], "chat-plasma-2")
