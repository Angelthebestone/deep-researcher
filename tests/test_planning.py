from __future__ import annotations

import unittest

from vigilador_tecnologico.integrations.gemini import GeminiAdapterError
from vigilador_tecnologico.services.planning import PlanningService


class _PlainTextPlannerAdapter:
    def generate_content(self, prompt, **kwargs):
        return {
            "text": (
                "Plan summary: Serial research plan for plasma gasification and biomass conversion.\n"
                "Gemini queries: plasma gasification for biomass reactor design; plasma torch syngas quality; biomass plasma gasification commercial deployments\n"
                "Mistral queries: plasma gasification for biomass reactor design; plasma torch syngas quality; biomass plasma gasification commercial deployments"
            )
        }


class _FailingPlannerAdapter:
    def generate_content(self, prompt, **kwargs):
        raise GeminiAdapterError("Gemini request timed out: The read operation timed out")


class PlanningServiceTest(unittest.TestCase):
    def test_create_research_plan_parses_plain_text(self):
        service = PlanningService()
        service.adapter = _PlainTextPlannerAdapter()  # type: ignore[assignment]

        plan, stage_context = service.create_research_plan(
            "Gasificación por plasma para biomasa",
            "Comprehensive technical and commercial assessment of plasma gasification technologies applied to biomass conversion.",
            3,
            2,
        )

        self.assertEqual(plan["target_technology"], "Gasificación por plasma para biomasa")
        self.assertEqual(plan["execution_mode"], "serial")
        self.assertEqual(plan["consolidation_model"], "gemini-3-flash-preview")
        self.assertEqual(len(plan["branches"]), 2)
        self.assertGreaterEqual(len(plan["branches"][0]["queries"]), 1)
        self.assertGreaterEqual(len(plan["branches"][1]["queries"]), 1)
        self.assertEqual(stage_context["stage"], "ResearchPlanCreated")
        self.assertIsNone(stage_context.get("fallback_reason"))

    def test_create_research_plan_uses_deterministic_fallback_on_timeout(self):
        service = PlanningService()
        service.adapter = _FailingPlannerAdapter()  # type: ignore[assignment]

        plan, stage_context = service.create_research_plan(
            "Gasificación por plasma para biomasa",
            "Comprehensive technical and commercial assessment of plasma gasification technologies applied to biomass conversion.",
            3,
            2,
        )

        self.assertEqual(plan["target_technology"], "Gasificación por plasma para biomasa")
        self.assertEqual(plan["execution_mode"], "serial")
        self.assertEqual(len(plan["branches"]), 2)
        self.assertTrue(all(branch["queries"] for branch in plan["branches"]))
        self.assertEqual(stage_context["stage"], "ResearchPlanCreated")
        self.assertEqual(stage_context.get("fallback_reason"), "planner_fallback")
