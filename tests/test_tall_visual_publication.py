"""Deterministic panel geometry, verified-subset integrity and safe diagnostics."""
from __future__ import annotations
import hashlib
import io
from PIL import Image, ImageDraw
import pytest
from app.services.visual_regions import slide_regions
from app.services.visual_publication import verified_subset, remove_chrome
from app.services.visual_contracts import VisionExtractionData
from app.services.visual_verifier import VerificationCheck, combine_checks, VisualVerificationFailed
from app.services.ingestion.failures import ingestion_stage, SourceIngestionFailed
from app.services.schemas import ContentUnit

def screenshot(irregular: bool = False) -> bytes:
    image = Image.new("RGB", (720, 1600), "black")
    draw = ImageDraw.Draw(image)
    for top in (160, 568, 976 if not irregular else 1010):
        draw.rectangle((0, top, 719, top + 407), fill=(159,159,159))
        draw.text((30, top+30), "Visible educational text", fill="black")
        draw.rectangle((0, top+388, 719, top+407), fill=(9,76,119))
    out = io.BytesIO(); image.save(out, format="PNG"); return out.getvalue()

def test_three_slide_regions_preserve_every_content_pixel_and_exclude_outer_ui() -> None:
    regions = slide_regions(screenshot())
    assert [r.bbox for r in regions] == [(0,160,720,568),(0,568,720,976),(0,976,720,1384)]
    assert all(Image.open(io.BytesIO(r.image)).size == (720,408) for r in regions)

def test_irregular_or_ordinary_layout_remains_whole() -> None:
    assert not slide_regions(screenshot(True))
    stream=io.BytesIO();Image.new("RGB",(720,1600),"white").save(stream,format="PNG")
    assert not slide_regions(stream.getvalue())

LINES = ["Feasibility and viability depends on the implementation resources available.",
         "Impact and benefits include the listed educational outcomes for learners."]

def evidence():
    data=VisionExtractionData(visible_text=LINES+["Invented statement", "Unreadable statement"], confidence=.9,content_kind="TEXT")
    checks=[VerificationCheck(claim_id=str(i),claim_type="visible_text",claim=line,
             status=status,reason="INDEPENDENT_VISUAL_"+reason,visible_support=line if status=="VERIFIED" else "")
            for i,(line,status,reason) in enumerate(zip(data.visible_text,
                 ["VERIFIED","VERIFIED","REJECTED","UNCERTAIN"],["SUPPORTED","SUPPORTED","CONTRADICTED","UNCERTAIN"]))]
    return data,combine_checks(checks,"INDEPENDENT_REVIEW_REQUIRED")

def test_only_independently_verified_subset_is_published() -> None:
    data,result=evidence();original=data.model_dump()
    subset=verified_subset(data,result);assert subset is not None
    clean,published=subset
    assert clean.visible_text==LINES and published.status=="VERIFIED"
    assert all(c.status=="VERIFIED" for c in published.checks)
    assert data.model_dump()==original
    assert result.status=="REJECTED" and len(result.uncertain_claims)==1

@pytest.mark.parametrize("defect",["fixture","scope","too_small","review_unavailable"])
def test_security_and_insufficient_evidence_cannot_be_salvaged(defect: str) -> None:
    data,result=evidence()
    if defect=="fixture":result=result.model_copy(update={"strategy":"FIXTURE_GROUND_TRUTH"})
    elif defect=="scope":result=result.model_copy(update={"checks":result.checks+[VerificationCheck(claim_type="source_scope",claim="foreign",status="REJECTED",reason="SOURCE_ANCHOR_SCOPE_MISMATCH")]})
    elif defect=="too_small":data=data.model_copy(update={"visible_text":[LINES[0]]})
    else:result=result.model_copy(update={"checks":[c.model_copy(update={"status":"UNCERTAIN","reason":"INDEPENDENT_VERIFIER_TIMEOUT"}) for c in result.checks]})
    assert verified_subset(data,result) is None

def test_known_branding_removed_but_educational_wps_discussion_preserved() -> None:
    data=VisionExtractionData(visible_text=["Powered by WPS Office","WPS Office can open presentation files.",*LINES],confidence=.9)
    clean,count=remove_chrome(data)
    assert count==1 and clean.visible_text==data.visible_text[1:]

def test_failure_retains_counts_and_fixed_reasons_without_claim_text() -> None:
    _,result=evidence()
    with pytest.raises(SourceIngestionFailed) as caught:
        with ingestion_stage("EXTRACTION"):
            raise VisualVerificationFailed(result)
    failure=caught.value.failure
    assert failure.stage=="VERIFICATION" and failure.code=="VISUAL_EVIDENCE_REJECTED"
    assert (failure.verified_claim_count,failure.uncertain_claim_count,failure.rejected_claim_count)==(2,1,1)
    assert failure.verification_reasons==["INDEPENDENT_VISUAL_CONTRADICTED","INDEPENDENT_VISUAL_UNCERTAIN"]
    assert "Invented statement" not in failure.model_dump_json()

def test_regions_use_shared_deadline_and_original_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import visual_evidence
    calls=[]
    def region_unit(image: bytes, **kwargs: object) -> ContentUnit:
        calls.append(kwargs)
        return ContentUnit(source_id="source",asset_id="asset",modality="image",text=LINES[0],provenance={"visual_verification":{"status":"VERIFIED"}})
    monkeypatch.setattr(visual_evidence,"visual_content_unit",region_unit)
    image=screenshot()
    units=visual_evidence.visual_content_units(image,source_id="source",asset_id="asset",source="slides.png",image_path="original.png")
    assert len(units)==3 and len({c["deadline"] for c in calls})==1
    assert all(u.provenance["original_image_sha256"]==hashlib.sha256(image).hexdigest() for u in units)
    assert all(c["image_path"]=="original.png" for c in calls)


def test_unrelated_colored_chart_bands_do_not_prove_slide_regions() -> None:
    image=Image.open(io.BytesIO(screenshot())).convert("RGB")
    ImageDraw.Draw(image).rectangle((0,956,719,975),fill=(180,10,10))
    out=io.BytesIO();image.save(out,format="PNG")
    assert not slide_regions(out.getvalue())


def test_atomic_table_with_one_uncertain_cell_is_fully_excluded() -> None:
    from app.services.visual_contracts import VisualTable
    data,result=evidence()
    data.tables=[VisualTable(headers=["Name"],rows=[["Ada"]])]
    checks=result.checks+[
        VerificationCheck(claim_type="table_headers",claim="Name",status="VERIFIED",reason="INDEPENDENT_VISUAL_SUPPORTED"),
        VerificationCheck(claim_type="table_cells",claim="Ada",status="UNCERTAIN",reason="INDEPENDENT_VISUAL_UNCERTAIN")]
    subset=verified_subset(data,combine_checks(checks,"INDEPENDENT_REVIEW_REQUIRED"))
    assert subset is not None and subset[0].tables==[]

def test_subset_gate_canonicalizes_only_retained_supported_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import visual_evidence,visual_router
    from app.core.config import settings
    data,result=evidence();data._actual_provider="cloudflare";data._actual_model=visual_router.MODELS["general"]
    class Router:
        def extract(self,*args: object,**kwargs: object) -> VisionExtractionData:
            return data
    class Reviewer:
        def verify(self,*args: object,**kwargs: object):
            return result
    monkeypatch.setattr(settings,"vision_provider","cloudflare")
    monkeypatch.setattr(visual_router,"get_visual_router",lambda:Router())
    unit=visual_evidence.visual_content_unit(screenshot(),source_id="source",asset_id="asset",source="slides.png",verifier=Reviewer())
    assert "Invented statement" not in unit.text and "Unreadable statement" not in unit.text
    assert unit.provenance["visual_verification"]["status"]=="VERIFIED"
    assert unit.provenance["original_verification_summary"]["verification_status"]=="REJECTED"
    assert unit.provenance["publication_policy"]=="independent-verified-subset-v1"


@pytest.mark.parametrize("count", [2,4,5,8])
def test_panel_detection_depends_on_repeated_geometry_not_three_slides(count: int) -> None:
    image=Image.new("RGB",(720,max(1500,320+408*count)),"black")
    draw=ImageDraw.Draw(image)
    for i in range(count):
        top=160+i*408
        draw.rectangle((0,top,719,top+407),fill=(159,159,159))
        draw.text((30,top+30),f"Educational panel {i}",fill="black")
        draw.rectangle((0,top+388,719,top+407),fill=(9,76,119))
    output=io.BytesIO();image.save(output,format="PNG")
    regions=slide_regions(output.getvalue())
    assert len(regions)==count
    assert regions[0].bbox[1]==160 and regions[-1].bbox[3]==160+408*count
