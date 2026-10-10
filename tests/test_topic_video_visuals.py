"""Visual regression checks for continuous topic storyboards, including MP4 frames."""
import numpy as np
import pytest

from app.core.config import settings
from app.services.video.scene_schema import ScenePlan, SceneType, VideoPlan
from app.services.video.topic_visuals import draw_topic_frame, scene_labels, visual_kind


def plan_for(topic, scene=None):
    scene = scene or ScenePlan(title="How it works", text="Input provides energy. The process changes the system. Output is produced.",
        narration="Input provides energy. The process changes the system. Output is produced.", duration_seconds=6)
    return VideoPlan(concept_id="example", concept_name=topic, scenes=[scene],
        provenance_kind="AI_ENRICHED", provenance={"visual_style":"topic_2d_v1"})


@pytest.mark.parametrize("topic,kind", [("Binary Search Trees","tree"), ("Photosynthesis","plant"),
    ("Water Cycle","water"), ("Solar System","orbit"), ("Binary Search","array"),
    ("Democracy","concept_map")])
def test_topic_visuals_remain_visible_and_change_during_narration(topic, kind):
    plan = plan_for(topic)
    scene = plan.scenes[0]
    assert visual_kind(topic, scene) == kind
    first = np.asarray(draw_topic_frame(plan, scene, .05))
    last = np.asarray(draw_topic_frame(plan, scene, .98))
    for frame in (first, last):
        assert frame.shape == (720,1280,3)
        # Ignore header, progress, captions and side cards: the actual teaching
        # illustration must be present near the end, not a frozen empty canvas.
        assert np.count_nonzero(frame[155:580,40:880].max(axis=2) > 150) > 1500
    assert np.count_nonzero(first != last) > 2000


def test_grounded_visuals_do_not_add_unsourced_domain_facts():
    scene = ScenePlan(diagram_type="source_cards",text="The supplied excerpt describes a leaf.")
    assert visual_kind("Photosynthesis",scene) == "concept_map"
    assert scene_labels(scene) == ["The supplied excerpt describes a leaf."]
    assert scene.evidence_references == []


def test_model_visual_layout_is_declarative_and_labels_are_bounded():
    scene = ScenePlan(visual_payload={"layout":"comparison","labels":["Left subtree","Right subtree"]})
    assert visual_kind("Trees",scene) == "comparison"
    assert scene_labels(scene) == ["Left subtree","Right subtree"]
    scene.visual_payload["labels"] = ["x"*200]*10
    assert len(scene_labels(scene)) == 5
    assert all(len(label) <= 80 for label in scene_labels(scene))


def test_encoded_storyboard_has_no_blank_scene_tails(tmp_path, monkeypatch):
    import cv2
    from app.services.video.manim_renderer import render_video_plan
    from app.services.video.video_compositor import probe_media
    monkeypatch.setattr(settings,"video_default_fps",6)
    scenes = [ScenePlan(scene_type=SceneType.EXPLANATION, title=title, text=text, duration_seconds=2)
        for title,text in [("Root and subtrees","Compare smaller and larger keys."),
                           ("Search example","Follow a branch to locate a key.")]]
    plan = plan_for("Binary Search Trees",scenes[0])
    plan.scenes = scenes
    plan.duration_seconds = plan.target_seconds = 4
    output = render_video_plan(plan,tmp_path/"continuous.mp4")
    assert float(probe_media(output)["format"]["duration"]) == pytest.approx(4,abs=.1)
    capture = cv2.VideoCapture(str(output))
    try:
        for seconds in (.1,1.8,2.1,3.8):
            capture.set(cv2.CAP_PROP_POS_MSEC,seconds*1000)
            ok,frame = capture.read()
            assert ok
            assert np.count_nonzero(frame[155:580,40:880].max(axis=2) > 150) > 1500
    finally:
        capture.release()
