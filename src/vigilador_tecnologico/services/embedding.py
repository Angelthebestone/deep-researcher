from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.contracts.models import EmbeddingArtifact, EmbeddingRelation
from vigilador_tecnologico.integrations import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMINI_EMBEDDING_MODEL,
    GEMINI_EMBEDDING_TIMEOUT_SECONDS,
)
from vigilador_tecnologico.integrations.retry import call_with_retry


@dataclass(slots=True)
class EmbeddingService:
    adapter: GeminiAdapter | None = None
    model: str = GEMINI_EMBEDDING_MODEL
    similarity_threshold: float = 0.82

    def embed_iteration(
        self,
        *,
        branch_id: str,
        iteration: int,
        query: str,
        target_technology: str,
        learnings: list[str],
        previous_embeddings: list[EmbeddingArtifact],
    ) -> EmbeddingArtifact:
        adapter = self._get_adapter()
        source_text = self._source_text(
            target_technology=target_technology,
            query=query,
            learnings=learnings,
        )
        response = call_with_retry(
            adapter.embed_content,
            source_text,
            attempts=1,
            timeout=GEMINI_EMBEDDING_TIMEOUT_SECONDS,
        )
        vector = self._parse_vector(response)
        embedding_id = uuid.uuid4().hex
        relations = self._build_relations(
            embedding_id=embedding_id,
            vector=vector,
            previous_embeddings=previous_embeddings,
        )
        return {
            "embedding_id": embedding_id,
            "branch_id": branch_id,
            "iteration": iteration,
            "query": query,
            "model": self.model,
            "source_text": source_text,
            "vector": vector,
            "relations": relations,
        }

    def _source_text(self, *, target_technology: str, query: str, learnings: list[str]) -> str:
        learnings_text = " | ".join(learning.strip() for learning in learnings if learning.strip())
        return (
            "task: clustering | query: "
            f"technology={target_technology}; query={query}; learnings={learnings_text}"
        )

    def _build_relations(
        self,
        *,
        embedding_id: str,
        vector: list[float],
        previous_embeddings: list[EmbeddingArtifact],
    ) -> list[EmbeddingRelation]:
        relations: list[EmbeddingRelation] = []
        for previous in previous_embeddings:
            previous_vector = previous.get("vector")
            if not isinstance(previous_vector, list) or not previous_vector:
                continue
            similarity = self._cosine_similarity(vector, previous_vector)
            if similarity < self.similarity_threshold:
                continue
            relations.append(
                {
                    "relation_id": uuid.uuid4().hex,
                    "source_embedding_id": embedding_id,
                    "target_embedding_id": str(previous["embedding_id"]),
                    "similarity": round(similarity, 6),
                    "reason": "semantic_similarity",
                }
            )
        return relations

    def _parse_vector(self, response: dict[str, Any]) -> list[float]:
        embeddings = response.get("embeddings")
        if isinstance(embeddings, list):
            for embedding in embeddings:
                if isinstance(embedding, dict):
                    values = embedding.get("values")
                    if isinstance(values, list) and values:
                        return [float(value) for value in values]
        embedding = response.get("embedding")
        if isinstance(embedding, dict):
            values = embedding.get("values")
            if isinstance(values, list) and values:
                return [float(value) for value in values]
        raise ValueError("Embedding response did not contain vector values.")

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if len(left) != len(right):
            size = min(len(left), len(right))
            left = left[:size]
            right = right[:size]
        numerator = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return 0.0
        return numerator / (left_norm * right_norm)

    def _get_adapter(self) -> GeminiAdapter:
        if self.adapter is None:
            self.adapter = GeminiAdapter(model=self.model)
        return self.adapter
