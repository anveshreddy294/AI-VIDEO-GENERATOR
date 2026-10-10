"""Saved-caption validation, independently mutated from measured scene metadata."""
import pytest

from app.services.video.caption_validation import CaptionValidationError, caption_text, validate_scene_captions
from app.services.video.scene_schema import NarrationSegment, ScenePlan, SceneTimelineEntry, VideoPlan


@pytest.fixture
def captions(tmp_path):
    plan = VideoPlan(concept_id="c",concept_name="Trees", scenes=[ScenePlan(scene_index=i) for i in range(2)],
        narration=[NarrationSegment(scene_index=0,text="Compare <keys> & values."),
                   NarrationSegment(scene_index=1,text="Choose the subtree.")])
    timeline = [SceneTimelineEntry(scene_id=s.scene_id,scene_index=i,start_seconds=i*2,
        end_seconds=(i+1)*2,duration_seconds=2) for i,s in enumerate(plan.scenes)]
    path = tmp_path/"captions.vtt"
    path.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nCompare &lt;keys&gt; &amp; values.\n\n"
                    "00:00:02.000 --> 00:00:04.000\nChoose the subtree.\n",encoding="utf-8")
    return path, plan, timeline


def test_valid_saved_captions_and_crlf_bom(captions):
    path,plan,timeline = captions
    validate_scene_captions(path,plan,timeline,4)
    path.write_bytes(b"\xef\xbb\xbf"+path.read_text(encoding="utf-8").replace("\n","\r\n").encode("utf-8"))
    validate_scene_captions(path,plan,timeline,4)


@pytest.mark.parametrize("before,after", [
    ("WEBVTT","SRT"), ("00:00:02.000 --> 00:00:04.000","00:00:01.900 --> 00:00:04.000"),
    ("00:00:04.000","00:00:04.100"), ("00:00:02.000 --> 00:00:04.000","00:00:02.020 --> 00:00:04.000"),
    ("00:00:02.000 --> 00:00:04.000","00:00:04.000 --> 00:00:02.000"),
    ("00:00:00.000","00:60:00.000"), ("Choose the subtree.","Unrelated narration."),
    ("Choose the subtree.","Choose the subtree.\n\n00:00:04.000 --> 00:00:05.000\nExtra cue"),
    ("Choose the subtree.","Choose\n\nthe subtree."), ("&lt;keys&gt;","<keys>"),
])
def test_malformed_drifted_overlapping_or_mismatched_cues_fail(captions,before,after):
    path,plan,timeline = captions
    path.write_text(path.read_text().replace(before,after),encoding="utf-8")
    with pytest.raises(CaptionValidationError,match="VIDEO_CAPTIONS_INVALID"):
        validate_scene_captions(path,plan,timeline,4)


@pytest.mark.parametrize("field,value", [("scene_id","wrong"),("scene_index",5),
    ("start_seconds",2.1),("end_seconds",3.9),("duration_seconds",1.9)])
def test_timeline_must_match_scene_identity_duration_and_continuity(captions,field,value):
    path,plan,timeline = captions
    setattr(timeline[1],field,value)
    with pytest.raises(CaptionValidationError):
        validate_scene_captions(path,plan,timeline,4)


@pytest.mark.parametrize("duration", [0,-1,float("inf"),float("nan"),4.1])
def test_invalid_final_video_duration_fails(captions,duration):
    path,plan,timeline = captions
    with pytest.raises(CaptionValidationError):
        validate_scene_captions(path,plan,timeline,duration)


def test_missing_non_utf8_and_oversized_caption_files_fail(captions):
    path,plan,timeline = captions
    for contents in (b"\xff", b"x"*(1024*1024+1)):
        path.write_bytes(contents)
        with pytest.raises(CaptionValidationError):
            validate_scene_captions(path,plan,timeline,4)
    path.unlink()
    with pytest.raises(CaptionValidationError):
        validate_scene_captions(path,plan,timeline,4)


def test_caption_text_contains_markup_and_blank_line_injection():
    assert caption_text("A & B\n\n<keys> --> values") == "A &amp; B &lt;keys&gt; → values"
