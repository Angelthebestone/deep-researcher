from __future__ import annotations

import unittest

from vigilador_tecnologico.services._text_utils import (
    coerce_text,
    extend_unique,
    extract_grounding_queries,
    extract_grounding_urls,
    is_valid_query,
    normalize_key,
    normalize_text_list,
    normalize_urls,
    optional_text,
)


class TextUtilsTest(unittest.TestCase):
    def test_optional_text_and_coerce_text(self) -> None:
        self.assertIsNone(optional_text(None))
        self.assertIsNone(optional_text("   "))
        self.assertEqual(optional_text(" ok "), "ok")
        self.assertEqual(coerce_text(None), "")
        self.assertEqual(coerce_text(" x "), "x")

    def test_normalize_text_list_and_urls(self) -> None:
        self.assertEqual(normalize_text_list([" a ", "", None, "b"]), ["a", "b"])
        self.assertEqual(normalize_urls(["https://a", "https://a", " https://b "]), ["https://a", "https://b"])

    def test_extend_unique_and_normalize_key(self) -> None:
        values = ["a", "b"]
        extend_unique(values, ["b", "c"])
        self.assertEqual(values, ["a", "b", "c"])
        self.assertEqual(normalize_key("", "  Fast API  "), "fast api")
        self.assertEqual(normalize_key(None, " "), "")

    def test_is_valid_query(self) -> None:
        self.assertFalse(is_valid_query(""))
        self.assertFalse(is_valid_query("short"))
        self.assertTrue(is_valid_query("fastapi python async framework"))

    def test_extract_grounding_urls_and_queries(self) -> None:
        response = {
            "candidates": [
                {
                    "groundingMetadata": {
                        "groundingChunks": [{"web": {"uri": "https://a"}}, {"web": {"uri": "https://a"}}],
                        "webSearchQueries": ["fastapi docs", "fastapi docs", "python api"],
                    }
                }
            ]
        }
        self.assertEqual(extract_grounding_urls(response), ["https://a"])
        self.assertEqual(extract_grounding_queries(response), ["fastapi docs", "python api"])


if __name__ == "__main__":
    unittest.main()
