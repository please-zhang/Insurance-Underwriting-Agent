"""Document retrieval tool backed by local ChromaDB."""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import chromadb

from agent.tools.base import BaseTool


class SimpleEmbeddingFunction:
    def __init__(self, dimensions: int = 64) -> None:
        self.dimensions = dimensions

    def __call__(self, input: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in input]

    def embed_query(self, input: list[str]) -> list[list[float]]:
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "simple_hash_embedding"

    @staticmethod
    def build_from_config(config: dict[str, Any]) -> "SimpleEmbeddingFunction":
        return SimpleEmbeddingFunction(dimensions=config.get("dimensions", 64))

    def get_config(self) -> dict[str, Any]:
        return {"dimensions": self.dimensions}

    def is_legacy(self) -> bool:
        return False

    def default_space(self) -> str:
        return "cosine"

    def supported_spaces(self) -> list[str]:
        return ["cosine", "l2", "ip"]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in self._tokens(text):
            vector[hash(token) % self.dimensions] += 1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def _tokens(self, text: str) -> list[str]:
        normalized = text.lower().strip()
        cjk_chars = [char for char in normalized if "\u4e00" <= char <= "\u9fff"]
        if cjk_chars:
            chars = [char for char in normalized if not char.isspace()]
            bigrams = [
                "".join(chars[index : index + 2])
                for index in range(len(chars) - 1)
                if len("".join(chars[index : index + 2])) == 2
            ]
            return chars + bigrams
        return re.findall(r"\w+", normalized)


class DocRetrieverTool(BaseTool):
    name = "doc_retriever"
    description = "从保险产品说明书和条款文档中检索与申请相关的内容。"
    input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索查询"},
            "product_code": {"type": "string", "description": "产品代码"},
            "top_k": {"type": "integer", "description": "返回结果数量", "default": 3},
        },
        "required": ["query"],
    }

    def __init__(
        self,
        docs_path: str = "data/docs/product_manual.md",
        persist_dir: str = "data/chroma_db",
        collection_name: str = "underwriting_docs",
    ) -> None:
        self.docs_path = Path(docs_path)
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=SimpleEmbeddingFunction(),
        )
        self._ensure_index()

    async def execute(
        self,
        *,
        query: str,
        product_code: str | None = None,
        top_k: int = 3,
    ) -> dict[str, Any]:
        if self.collection.count() == 0:
            return {"passages": []}

        result = await self._query_async(query=query, top_k=top_k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        passages = []

        for content, metadata, distance in zip(documents, metadatas, distances):
            passages.append(
                {
                    "content": content,
                    "source": metadata.get("source", "unknown"),
                    "relevance_score": round(max(0.0, 1.0 - float(distance)), 4),
                }
            )

        return {"passages": passages}

    async def _query_async(self, *, query: str, top_k: int) -> dict[str, Any]:
        from asyncio import to_thread

        return await to_thread(
            self.collection.query,
            query_texts=[query],
            n_results=top_k,
        )

    def _ensure_index(self) -> None:
        if not self.docs_path.exists() or self.collection.count() > 0:
            return

        content = self.docs_path.read_text(encoding="utf-8")
        chunks = self._chunk_text(content)
        if not chunks:
            return

        ids = [f"doc-{index}" for index in range(len(chunks))]
        metadatas = [{"source": f"product_manual#{index + 1}"} for index in range(len(chunks))]
        self.collection.add(ids=ids, documents=chunks, metadatas=metadatas)

    def _chunk_text(self, content: str) -> list[str]:
        return [chunk.strip() for chunk in re.split(r"\n\s*\n", content) if chunk.strip()]
