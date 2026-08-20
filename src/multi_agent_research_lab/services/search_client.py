"""Search client abstraction for ResearcherAgent."""

import json
import logging
import urllib.request
from pathlib import Path
from typing import Any

from multi_agent_research_lab.core.config import Settings, get_settings
from multi_agent_research_lab.core.schemas import SourceDocument

logger = logging.getLogger(__name__)


class SearchClient:
    """Provider-agnostic search client with Tavily and local corpus support."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.tavily_key = self.settings.tavily_api_key
        self.timeout = float(self.settings.timeout_seconds)
        self._corpus_dir = Path("ai_agent_offline_research_corpus_v2/topics")

    def _search_tavily(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search online using Tavily API."""
        url = "https://api.tavily.com/search"
        payload = json.dumps(
            {
                "api_key": self.tavily_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "basic",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "MultiAgentResearchLab/1.0",
            },
        )

        with urllib.request.urlopen(req, timeout=self.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

        documents: list[SourceDocument] = []
        for item in data.get("results", []):
            documents.append(
                SourceDocument(
                    title=item.get("title", "Untitled Source"),
                    url=item.get("url"),
                    snippet=item.get("content", ""),
                    metadata={"score": item.get("score"), "source": "tavily"},
                )
            )
        return documents

    def _search_offline_corpus(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search local offline research corpus by topic and keyword matching."""
        documents: list[SourceDocument] = []
        query_words = set(query.lower().split())

        if self._corpus_dir.exists():
            scored_articles: list[tuple[int, dict[str, Any], str]] = []
            for json_file in self._corpus_dir.glob("*.json"):
                try:
                    data = json.loads(json_file.read_text(encoding="utf-8"))
                    topic_name = data.get("topic", {}).get("name", "")
                    articles = data.get("knowledge_base", {}).get("knowledge_articles", [])
                    source_docs = data.get("knowledge_base", {}).get("source_documents", [])

                    for art in articles:
                        title = art.get("title", "")
                        content = art.get("content", "")
                        text = f"{topic_name} {title} {content}".lower()
                        score = sum(1 for w in query_words if w in text)
                        art_id = art.get("article_id", "")
                        scored_articles.append(
                            (
                                score,
                                {
                                    "title": f"{topic_name}: {title}",
                                    "url": f"corpus://{json_file.stem}/{art_id}",
                                    "snippet": content[:400]
                                    + ("..." if len(content) > 400 else ""),
                                    "metadata": {"article_id": art_id, "type": "article"},
                                },
                                json_file.stem,
                            )
                        )

                    for sdoc in source_docs:
                        title = sdoc.get("title", "")
                        summary = sdoc.get("summary", sdoc.get("snippet", ""))
                        text = f"{topic_name} {title} {summary}".lower()
                        score = sum(1 for w in query_words if w in text)
                        src_id = sdoc.get("source_id", "")
                        doc_url = sdoc.get("url") or f"corpus://{json_file.stem}/{src_id}"
                        scored_articles.append(
                            (
                                score,
                                {
                                    "title": title,
                                    "url": doc_url,
                                    "snippet": summary[:400]
                                    + ("..." if len(summary) > 400 else ""),
                                    "metadata": {"source_id": src_id, "type": "source_doc"},
                                },
                                json_file.stem,
                            )
                        )
                except Exception as exc:
                    logger.debug("Failed to read %s: %s", json_file, exc)

            scored_articles.sort(key=lambda x: x[0], reverse=True)
            for _, doc_dict, _ in scored_articles[:max_results]:
                documents.append(SourceDocument(**doc_dict))

        # Fallback if no corpus or no matches
        if not documents:
            documents = [
                SourceDocument(
                    title=f"Research Overview: {query}",
                    url="local://synthesis/overview",
                    snippet=(
                        f"Comprehensive overview and state-of-the-art developments for '{query}'. "
                        "Key mechanisms include architectural modularity, structured handoffs, "
                        "and retrieval grounding."
                    ),
                    metadata={"source": "local_mock"},
                ),
                SourceDocument(
                    title=f"Methodology and Benchmarks for {query}",
                    url="local://synthesis/benchmarks",
                    snippet=(
                        f"Evaluation framework and comparative study covering {query}. "
                        "Highlights trade-offs between precision, latency, and context density."
                    ),
                    metadata={"source": "local_mock"},
                ),
            ]

        return documents[:max_results]

    def search(self, query: str, max_results: int = 5) -> list[SourceDocument]:
        """Search for documents relevant to a query."""
        if self.tavily_key:
            try:
                results = self._search_tavily(query, max_results=max_results)
                if results:
                    return results
            except Exception as exc:
                logger.warning("Tavily search failed (%s), falling back to offline corpus", exc)

        return self._search_offline_corpus(query, max_results=max_results)
