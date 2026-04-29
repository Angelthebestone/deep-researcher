from __future__ import annotations

import json
import unittest

import vigilador_tecnologico.services.prompt_engineering as prompt_engineering_module
from vigilador_tecnologico.services.prompt_engineering import PromptEngineeringService


class _GarbledPromptAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self.last_kwargs: dict[str, object] = {}
        self.last_parts: object | None = None

    def generate_content_parts(self, parts, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        self.last_parts = parts
        payload = {
            "response": (
                "Refined query: Conduct a comprehensive technical and market analysis of Plasma Gasification technology applied to biomass feedstock. Focus on technical parameters such as="
            ),
        }
        return {"text": json.dumps(payload)}


class PromptEngineeringServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_improve_query_uses_explicit_deterministic_fallback_on_truncated_payload(self):
        adapter = _GarbledPromptAdapter()
        service = PromptEngineeringService()
        service.adapter = adapter

        captured: dict[str, object] = {}

        def _call_with_retry_spy(func, /, *args, **kwargs):
            captured.update(kwargs)
            return func(*args, **kwargs)

        original_call_with_retry = prompt_engineering_module.call_with_retry
        prompt_engineering_module.call_with_retry = _call_with_retry_spy
        self.addCleanup(lambda: setattr(prompt_engineering_module, "call_with_retry", original_call_with_retry))

        result = await service.improve_query("Plasma Gasification for Biomass")

        self.assertEqual(
            result,
            {
                "refined_query": (
                    "Analyze Plasma Gasification for Biomass as a technology surveillance brief. "
                    "Focus on technical principles, operating constraints, commercial adoption, "
                    "vendors, risks, comparative alternatives, and recent developments."
                ),
                "target_technology": "Plasma Gasification for Biomass",
                "suggested_breadth": 3,
                "suggested_depth": 2,
                "keywords": [
                    "Plasma Gasification for Biomass",
                    "technical principles",
                    "commercial adoption",
                    "vendor landscape",
                    "risks",
                    "alternative technologies",
                ],
                "fallback_reason": "invalid_json",
            },
        )
        self.assertEqual(adapter.calls, 1)
        self.assertEqual(adapter.last_parts, [{"text": "Plasma Gasification for Biomass"}])
        self.assertNotIn("tools", adapter.last_kwargs)
        self.assertIn("generation_config", adapter.last_kwargs)
        self.assertIn("system_instruction", adapter.last_kwargs)
        self.assertEqual(adapter.last_kwargs.get("timeout"), 40.0)
        self.assertEqual(captured.get("attempts"), 1)
        self.assertNotIn("thinkingConfig", adapter.last_kwargs["generation_config"])
        self.assertNotIn("responseSchema", adapter.last_kwargs["generation_config"])
        self.assertIn("plain text brief", adapter.last_kwargs["system_instruction"])

    async def test_improve_query_parses_plain_text_output(self):
        class _PlainTextAdapter(_GarbledPromptAdapter):
            def generate_content_parts(self, parts, **kwargs):
                self.calls += 1
                self.last_kwargs = kwargs
                self.last_parts = parts
                return {
                    "text": (
                        "Refined query: Assess plasma gasification for biomass feedstock.\n"
                        "Target technology: Plasma Gasification for Biomass\n"
                        "Breadth: 4\n"
                        "Depth: 2\n"
                        "Keywords: plasma gasification; biomass feedstock; plasma torch"
                    )
                }

        adapter = _PlainTextAdapter()
        service = PromptEngineeringService()
        service.adapter = adapter

        result = await service.improve_query("Plasma Gasification for Biomass")

        self.assertEqual(result["target_technology"], "Plasma Gasification for Biomass")
        self.assertEqual(result["suggested_breadth"], 4)
        self.assertEqual(result["suggested_depth"], 2)
        self.assertIn("Assess plasma gasification for biomass feedstock.", result["refined_query"])
        self.assertIn("plasma gasification", " ".join(result["keywords"]).lower())
