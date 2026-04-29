from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any, NotRequired, get_origin, get_type_hints

from vigilador_tecnologico.contracts.models import (
    AnalysisStreamEvent,
    AlternativeTechnology,
    ComparisonItem,
    DocumentScopeItem,
    EvidenceSpan,
    InventoryItem,
    OperationEvent,
    OperationRecord,
    RecommendationItem,
    ResearchPlan,
    ResearchPlanBranch,
    RiskItem,
    SourceItem,
    TechnologyMention,
    TechnologyResearch,
    TechnologyReport,
)


SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schemas"


class SchemaContractAlignmentTest(unittest.TestCase):
    def test_technology_mention_schema_matches_contract(self) -> None:
        schema = self._load_schema("technology_mention.schema.json")
        self._assert_typeddict_schema_matches(
            schema,
            TechnologyMention,
            enum_fields={
                "source_type": ["pdf", "image", "docx", "pptx", "sheet", "text"],
                "category": ["language", "framework", "database", "cloud", "tool", "other"],
            },
        )
        self._assert_typeddict_schema_matches(
            schema["$defs"]["EvidenceSpan"],
            EvidenceSpan,
            enum_fields={"evidence_type": ["text", "ocr", "table", "figure", "caption"]},
        )

    def test_technology_research_schema_matches_contract(self) -> None:
        schema = self._load_schema("technology_research.schema.json")
        self._assert_typeddict_schema_matches(
            schema,
            TechnologyResearch,
            enum_fields={"status": ["current", "deprecated", "emerging", "unknown"]},
            datetime_fields={"checked_at": "string", "release_date": ["string", "null"]},
        )
        self.assertEqual(schema["properties"]["breadth"]["type"], "integer")
        self.assertEqual(schema["properties"]["breadth"]["minimum"], 1)
        self.assertEqual(schema["properties"]["depth"]["type"], "integer")
        self.assertEqual(schema["properties"]["depth"]["minimum"], 1)
        self.assertEqual(schema["properties"]["stage_context"]["type"], "object")
        self.assertTrue(schema["properties"]["stage_context"]["additionalProperties"])
        self._assert_typeddict_schema_matches(
            schema["$defs"]["AlternativeTechnology"],
            AlternativeTechnology,
            enum_fields={"status": ["current", "deprecated", "emerging", "unknown"]},
        )

    def test_technology_report_schema_matches_contract(self) -> None:
        schema = self._load_schema("technology_report.schema.json")
        self._assert_typeddict_schema_matches(
            schema,
            TechnologyReport,
            datetime_fields={"generated_at": "string"},
        )
        self._assert_typeddict_schema_matches(schema["$defs"]["DocumentScopeItem"], DocumentScopeItem, datetime_fields={"uploaded_at": ["string", "null"]})
        self._assert_typeddict_schema_matches(
            schema["$defs"]["InventoryItem"],
            InventoryItem,
            enum_fields={
                "category": ["language", "framework", "database", "cloud", "tool", "other"],
                "status": ["current", "deprecated", "emerging", "unknown"],
            },
        )
        self._assert_typeddict_schema_matches(
            schema["$defs"]["ComparisonItem"],
            ComparisonItem,
            enum_fields={"market_status": ["current", "deprecated", "emerging", "unknown"]},
        )
        self._assert_typeddict_schema_matches(
            schema["$defs"]["RiskItem"],
            RiskItem,
            enum_fields={"severity": ["low", "medium", "high", "critical"]},
        )
        self._assert_typeddict_schema_matches(
            schema["$defs"]["RecommendationItem"],
            RecommendationItem,
            enum_fields={
                "priority": ["critical", "high", "medium", "low"],
                "effort": ["low", "medium", "high"],
                "impact": ["low", "medium", "high"],
            },
        )
        self._assert_typeddict_schema_matches(
            schema["$defs"]["SourceItem"],
            SourceItem,
            datetime_fields={"retrieved_at": "string"},
        )

    def test_operation_event_schema_matches_contract(self) -> None:
        schema = self._load_schema("operation_event.schema.json")
        self._assert_typeddict_schema_matches(
            schema,
            OperationEvent,
            enum_fields={
                "operation_type": ["research", "analysis"],
                "status": ["queued", "running", "completed", "failed"],
            },
            datetime_fields={"created_at": "string"},
        )
        self.assertEqual(schema["properties"]["details"]["type"], "object")
        self.assertTrue(schema["properties"]["details"]["additionalProperties"])

    def test_operation_record_schema_matches_contract(self) -> None:
        schema = self._load_schema("operation_record.schema.json")
        self._assert_typeddict_schema_matches(
            schema,
            OperationRecord,
            enum_fields={
                "operation_type": ["research", "analysis"],
                "status": ["queued", "running", "completed", "failed"],
            },
            datetime_fields={"created_at": "string", "updated_at": "string"},
        )
        self.assertEqual(schema["properties"]["details"]["type"], "object")
        self.assertTrue(schema["properties"]["details"]["additionalProperties"])

    def test_analysis_stream_event_schema_matches_contract(self) -> None:
        schema = self._load_schema("analysis_stream_event.schema.json")
        self._assert_typeddict_schema_matches(schema, AnalysisStreamEvent)
        self.assertEqual(schema["properties"]["details"]["type"], "object")
        self.assertTrue(schema["properties"]["details"]["additionalProperties"])
        self.assertEqual(schema["properties"]["stage_context"]["type"], "object")
        self.assertTrue(schema["properties"]["stage_context"]["additionalProperties"])

    def test_research_plan_schema_matches_contract(self) -> None:
        schema = self._load_schema("research_plan.schema.json")
        self._assert_typeddict_schema_matches(
            schema,
            ResearchPlan,
            enum_fields={"execution_mode": ["serial"]},
        )
        self._assert_typeddict_schema_matches(
            schema["$defs"]["ResearchPlanBranch"],
            ResearchPlanBranch,
            enum_fields={"provider": ["gemini_grounded", "mistral_web_search"]},
        )

    def _load_schema(self, filename: str) -> dict[str, Any]:
        return json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))

    def _assert_typeddict_schema_matches(
        self,
        schema: dict[str, Any],
        contract: type,
        *,
        enum_fields: dict[str, list[str]] | None = None,
        datetime_fields: dict[str, list[str] | str] | None = None,
    ) -> None:
        enum_fields = enum_fields or {}
        datetime_fields = datetime_fields or {}
        hints = get_type_hints(contract, include_extras=True)
        required_keys = {
            name
            for name, annotation in hints.items()
            if get_origin(annotation) is not NotRequired
        }

        self.assertFalse(schema.get("additionalProperties", True))
        self.assertEqual(set(schema["properties"]), set(hints))
        self.assertEqual(set(schema["required"]), required_keys)

        for field_name, expected_values in enum_fields.items():
            self.assertEqual(schema["properties"][field_name]["enum"], expected_values)

        for field_name, expected_type in datetime_fields.items():
            property_schema = schema["properties"][field_name]
            self.assertEqual(property_schema["type"], expected_type)
            self.assertEqual(property_schema["format"], "date-time")
