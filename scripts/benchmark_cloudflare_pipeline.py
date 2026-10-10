"""Synthetic offline orchestration benchmark. Providers are mocks, never real latency.

Measures parsing/caching overhead, call counts, provenance and optional-image recovery.
Run check_cloudflare_runtime.py separately for real Cloudflare evidence.
"""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json
import tempfile
import time
from unittest.mock import patch
import pymupdf as fitz
from PIL import Image, ImageDraw
import io

from app.core.config import settings
from app.core.reasoning import ProviderFailure
from app.services.dispatcher import dispatch
from app.services.visual_router import VisualModelRouter, VisualScope, visual_scope, CloudResult, MODELS, VisualSignals
from app.services.visual_contracts import VisionExtractionData
from app.services.visual_verifier import VisualEvidenceVerifier, combine_checks

DATA = {"visible_text":["Binary Search Tree", "Root 10", "Left child 5", "Right child 15"],
    "content_kind":"TEXT", "confidence":0.9}


class Cloud:
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail
    def generate(self, image_uri, tier, triage, deadline, **kwargs):
        self.calls += 1
        if self.fail:
            raise ProviderFailure("TIMEOUT",True)
        return CloudResult(DATA, "synthetic-request", MODELS[tier], 0.0)


class Local:
    def __init__(self):
        self.calls = 0
    def generate(self,image,source,deadline):
        self.calls += 1
        result = VisionExtractionData.model_validate(DATA)
        result._actual_provider, result._actual_model = "ollama", "gemma3:4b"
        return result


class Review:
    def __init__(self):
        self.calls = 0
    def verify(self, image, claims, extraction, provenance):
        self.calls += 1
        return combine_checks([c.model_copy(update={"status":"VERIFIED","reason":"MOCK_PIXEL_REVIEW","visible_support":c.claim}) for c in claims],"INDEPENDENT_REVIEW_REQUIRED")


def main():
    image = Image.new("RGB",(800,300),"white")
    ImageDraw.Draw(image).text((40,40),"Binary Search Tree\nRoot 10\nLeft child 5\nRight child 15", fill="black",font_size=28)
    buf = io.BytesIO()
    image.save(buf,format="PNG")
    with tempfile.TemporaryDirectory(prefix="visualai-benchmark-") as directory:
        root = Path(directory)
        image_path = root / "diagram.png"
        image_path.write_bytes(buf.getvalue())
        documents = {}
        for name, count, native, embedded in [("text_pdf",1,True,False),("scanned_pdf",1,False,True),("embedded_pdf",3,True,True)]:
            doc = fitz.open()
            for _ in range(count):
                page = doc.new_page()
                if native:
                    page.insert_text((50,50),"A binary search tree orders keys. Smaller keys go left; larger keys go right.")
                if embedded:
                    page.insert_image(fitz.Rect(50,100,550,300),stream=buf.getvalue())
            path = root / (name + ".pdf")
            doc.save(path)
            doc.close()
            documents[name] = path
        cases = [("small_text_pdf",documents["text_pdf"],None,False),
            ("scanned_pdf",documents["scanned_pdf"],None,False),
            ("simple_diagram",image_path,VisualSignals(semantic_kind="DIAGRAM"),False),
            ("complex_diagram",image_path,VisualSignals(complexity="COMPLEX"),False),
            ("multipage_embedded_pdf",documents["embedded_pdf"],None,False),
            ("provider_timeout",image_path,None,True)]
        for index,(name,path,signals,fail) in enumerate(cases):
            cloud,local,review = Cloud(fail),Local(),Review()
            router = VisualModelRouter(cloud,local,local_fallback_enabled=True)
            started = time.perf_counter()
            with patch.object(settings,"vision_provider","cloudflare"), patch.object(settings,"upload_dir",root/"assets"), patch.object(settings,"cloudflare_retry_backoff",0), \
                 patch("app.services.visual_router._router",router), \
                 patch("app.services.independent_visual_verifier.configured_visual_verifier",lambda **kw:VisualEvidenceVerifier(review)), \
                 visual_scope(VisualScope(user_id="synthetic-benchmark",source_id=str(index),source_version=1)):
                result = dispatch(path,str(index),"asset-"+str(index),routing_signals=signals)
            assert result.units and all(unit.source_id == str(index) for unit in result.units)
            print(json.dumps({"case":name,"mode":"MOCK_PROVIDERS","elapsed_ms":round((time.perf_counter()-started)*1000,3),
                "extraction_cloud_calls":cloud.calls,"local_fallback_calls":local.calls,"mock_review_calls":review.calls,
                "content_units":len(result.units),"pages":sorted({u.page_number for u in result.units if u.page_number}),
                "cache_hits":sum(u.provenance.get("routing",{}).get("cache_hit",False) for u in result.units)}))


if __name__ == "__main__":
    main()
