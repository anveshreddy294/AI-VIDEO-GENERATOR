"""KnowledgeSource adapters; public network requests are restricted to Wikipedia."""
import json
import time
from typing import Protocol
from urllib.parse import quote
import requests
from modules.learning.schemas import Source
from modules.ingestion.service import chunk_text
from modules.llm.provider import ProviderClient
from modules.config import NVIDIA_PLANNER_MODEL


class KnowledgeSource(Protocol):
    def obtain(self, topic): ...


class TrustedTopicSource:
    def __init__(self, store):
        self.store = store

    def obtain(self, topic):
        key = "wikipedia:" + topic.strip().lower()
        with self.store.connect() as db:
            row = db.execute("SELECT payload,created FROM cache WHERE key=?", (key,)).fetchone()
        if row and time.time() - row["created"] < 86400 * 7:
            pages = json.loads(row["payload"])
        else:
            response = requests.get("https://en.wikipedia.org/w/api.php",
                params={"action": "query", "format": "json", "generator": "search",
                    "gsrsearch": topic, "gsrlimit": 2, "prop": "extracts", "explaintext": 1,
                    "exintro": 1, "exlimit": "max"},
                headers={"User-Agent": "AICARLS/1.0 educational hackathon prototype"}, timeout=12)
            response.raise_for_status()
            pages = list(response.json().get("query", {}).get("pages", {}).values())
            pages = [{"title": p["title"], "extract": p.get("extract", "")[:18000]} for p in pages
                     if len(p.get("extract", "")) >= 100]
            if not pages:
                raise ValueError("Public source returned no usable evidence")
            with self.store.connect() as db:
                db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?)", (key, json.dumps(pages), time.time()))
        sources, chunks = [], []
        for page in pages:
            source = Source(title=page["title"], source_type="trusted_topic",
                url="https://en.wikipedia.org/wiki/" + quote(page["title"].replace(" ", "_")),
                trust_label="public_reference_review_recommended")
            sources.append(source)
            chunks.extend(chunk_text(page["extract"], source))
        return sources, chunks


class GeneratedLessonSource:
    def obtain(self, topic):
        text = ProviderClient().chat(NVIDIA_PLANNER_MODEL, [
            {"role": "system", "content": "Write a concise educational packet. Clearly state uncertainty. "
             "Include definitions, key facts, examples, prerequisites and misconceptions. No external citations."},
            {"role": "user", "content": topic}], max_tokens=3000)
        source = Source(title="AI-generated lesson knowledge", source_type="generated",
                        externally_grounded=False, trust_label="generated_not_externally_grounded")
        return [source], chunk_text(text, source)


class BundledCurriculumSource:
    def __init__(self, subject=None, document_id=None):
        self.subject, self.document_id = subject, document_id

    def obtain(self, topic):
        from modules.retrieval.pageindex_retriever import retrieve_curriculum
        result = retrieve_curriculum(topic, subject=self.subject, document_id=self.document_id)
        if not result.get("matched"):
            raise ValueError("Bundled curriculum has insufficient evidence")
        source = Source(title=result["document_id"], source_type="curriculum",
                        trust_label=result.get("retrieval_mode", "pageindex"))
        chunks = []
        for section in result["sections"]:
            chunks.extend(chunk_text(section["content"], source, section["start_page"]))
        return [source], chunks


class UploadedMaterialSource:
    def __init__(self, knowledge):
        self.knowledge = knowledge

    def obtain(self, topic):
        return self.knowledge.sources, self.knowledge.source_chunks
