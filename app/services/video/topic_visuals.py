"""Local 2D teaching illustrations; no remote images or model-generated code.

Modern educational scenes stay visible for every frame of their measured audio.
Illustrations are schematic examples, never additional source evidence.
"""
from __future__ import annotations

import math
import re

from .scene_schema import SceneType


def visual_kind(topic: str, scene) -> str:
    topic = topic.casefold().strip()
    # Source-grounded excerpts retain only source-derived concept cards. These
    # illustrative domain presets are selected only for AI-enriched lessons.
    if scene.diagram_type == "source_cards":
        return "concept_map"
    if scene.diagram_type == "force_box":
        return "force_box"
    if "binary search tree" in topic or topic == "bst":
        return "tree"
    if "photosynthesis" in topic:
        return "plant"
    if "water cycle" in topic:
        return "water"
    if "solar system" in topic or "planetary orbit" in topic:
        return "orbit"
    if "binary search" in topic or "sorting" in topic or "array" in topic:
        return "array"
    return scene.visual_payload.get("layout", "concept_map")


def scene_labels(scene) -> list[str]:
    supplied = scene.visual_payload.get("labels") or scene.summary_points
    if supplied:
        return [str(label)[:80] for label in supplied[:5]]
    # Small visual labels, not a duplicate wall of narration.
    parts = re.split(r"(?<=[.!?;])\s+|\n+", scene.text or scene.narration or scene.title or "")
    return [" ".join(part.split()[:7])[:80] for part in parts if part.strip()][:5] or ["Overview"]


def draw_topic_frame(plan, scene, ratio: float, *, font=None):
    """Return a bounded 1280x720 frame. No blank outro or text-only main panel."""
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (1280, 720), "#101a2b")
    draw = ImageDraw.Draw(image)
    if font is None:
        for name in ("DejaVuSans.ttf", "C:/Windows/Fonts/arial.ttf"):
            try:
                font = ImageFont.truetype(name, 24)
                break
            except OSError:
                continue
    if font:
        draw.font = font
    blue, yellow, white, muted = "#60a5fa", "#facc15", "#f1f5f9", "#94a3b8"

    def text(x, y, value, width=450, lines=2, color=white):
        words = str(value).split()
        rows, row = [], ""
        for word in words:
            candidate = (row + " " + word).strip()
            if draw.textbbox((0, 0), candidate)[2] > width and row:
                rows.append(row)
                row = word
            else:
                row = candidate
        if row:
            rows.append(row)
        for n, line in enumerate(rows[:lines]):
            if n == lines-1 and len(rows) > lines:
                line = line.rstrip(".,") + "…"
            # Also contain unbroken identifiers and long translated words.
            if draw.textbbox((0, 0), line)[2] > width:
                while line and draw.textbbox((0, 0), line + "…")[2] > width:
                    line = line[:-1]
                line += "…"
            draw.text((x, y+n*32), line, fill=color)

    def arrow(a, b, color=blue):
        draw.line([a, b], fill=color, width=5)
        angle = math.atan2(b[1]-a[1], b[0]-a[0])
        draw.polygon([b, (b[0]-16*math.cos(angle-.45), b[1]-16*math.sin(angle-.45)),
                          (b[0]-16*math.cos(angle+.45), b[1]-16*math.sin(angle+.45))], fill=color)

    labels = scene_labels(scene)
    # 3–5 visual beats per scene, plus continuous motion within illustrations.
    beat_count = max(3, min(5, math.ceil(scene.duration_seconds/4)))
    beat = min(beat_count-1, int(max(0, min(.999999, ratio))*beat_count))
    active = beat % len(labels)
    draw.rounded_rectangle((28, 24, 1252, 118), radius=20, fill="#192940")
    text(52, 38, plan.concept_name, width=1120, lines=1, color=blue)
    text(52, 74, scene.title or scene.scene_type.value.title(), width=1120, lines=1)
    # Main illustration takes most of the frame; narration lives in captions.
    draw.rounded_rectangle((28, 140, 884, 588), radius=24, fill="#142238")
    draw.rounded_rectangle((904, 140, 1252, 588), radius=24, fill="#192940")
    text(928, 164, "KEY IDEA", width=295, lines=1, color=blue)
    text(928, 215, labels[active], width=290, lines=4, color=yellow)
    for i in range(beat_count):
        draw.ellipse((932+i*36, 535, 946+i*36, 549), fill=yellow if i == beat else "#334155")
    kind = visual_kind(plan.concept_name, scene)
    if kind == "tree":
        nodes = [(450, 210), (260, 340), (650, 340), (165, 490), (355, 490), (560, 490), (755, 490)]
        values = [10, 5, 15, 3, 7, 12, 18]
        path = [0, 1, 4]
        worked = scene.diagram_type == "binary_search_tree"
        selected = path[min(2, int(ratio*3))] if worked else min(6, beat*2)
        for i, (x,y) in enumerate(nodes):
            if i:
                draw.line([nodes[(i-1)//2], (x,y)], fill=blue, width=4)
        for i, (x,y) in enumerate(nodes):
            draw.ellipse((x-34,y-34,x+34,y+34), fill="#213b58", outline=yellow if i == selected else blue, width=5)
            text(x-16,y-15,str(values[i]),width=60,lines=1)
        text(60, 550, "Illustrative tree" + (" · search for 7" if worked else " · smaller left, larger right"), width=790, lines=1, color=muted)
    elif kind == "plant":
        # Stable photosynthesis schematic; moving particles illustrate inputs.
        draw.line([(450,510),(450,300)], fill="#4ade80", width=16)
        draw.ellipse((320,310,460,385), fill="#16a34a")
        draw.ellipse((445,270,590,350), fill="#22c55e")
        draw.polygon([(370,510),(530,510),(500,565),(400,565)], fill="#b77945")
        draw.ellipse((100,190,190,280),fill=yellow)
        arrow((200,250),(360,320),yellow)
        arrow((180+int(ratio*35),425),(395,390))
        arrow((520,350),(745,300),"#4ade80")
        text(80,160,"Sunlight",width=180,lines=1)
        text(55,460,"Water + CO2",width=300,lines=1)
        text(600,240,"Oxygen",width=200,lines=1)
        text(590,460,"Sugars",width=200,lines=1)
        text(60,550,"Photosynthesis · schematic",width=790,lines=1,color=muted)
    elif kind == "water":
        draw.rectangle((65,480,840,560),fill="#0369a1")
        for x in range(90,810,70):
            draw.arc((x+int(ratio*20),470,x+65+int(ratio*20),500),180,360,fill=blue,width=3)
        for x in (450,500,550):
            draw.ellipse((x,190,x+100,260),fill="#cbd5e1")
        arrow((205,450),(260,250),yellow)
        arrow((320,220),(440,220))
        arrow((625,270),(690,455))
        text(65,295,"Evaporation",width=220,lines=1)
        text(390,160,"Condensation",width=300,lines=1)
        text(605,340,"Precipitation",width=235,lines=1)
        text(325,520,"Collection",width=250,lines=1)
    elif kind == "orbit":
        center = (450,365)
        draw.ellipse((410,325,490,405),fill=yellow)
        for i,radius in enumerate((95,145,200)):
            draw.ellipse((450-radius,365-radius,450+radius,365+radius),outline="#334b68",width=3)
            angle = ratio*math.tau/(i+1) + i*1.7
            x,y = 450+radius*math.cos(angle),365+radius*math.sin(angle)
            draw.ellipse((x-15,y-15,x+15,y+15),fill=(blue,"#4ade80","#fb923c")[i])
        text(65,550,"Illustrative orbits · sizes and distances not to scale",width=790,lines=1,color=muted)
    elif kind == "force_box":
        x = 240+int(ratio*270)
        draw.rectangle((x,295,x+120,415),fill="#2563eb",outline=blue,width=4)
        text(x+10,335,scene.object_label or "Mass",width=105,lines=1)
        arrow((x-140,355),(x-10,355),yellow)
        text(x-145,285,scene.force_label or "Force",width=220,lines=1,color=yellow)
        text(65,520,scene.acceleration_label or "Acceleration in the force direction",width=790,lines=1,color=muted)
    elif kind == "array":
        values = [2,5,8,12,16,23,38]
        for i,value in enumerate(values):
            x = 70+i*110
            draw.rounded_rectangle((x,300,x+95,395),radius=12,fill="#213b58",outline=yellow if i == beat%7 else blue,width=4)
            text(x+25,330,str(value),width=65,lines=1)
            text(x+35,415,str(i),width=60,lines=1,color=muted)
        text(65,520,"Illustrative ordered array · values and indices",width=790,lines=1,color=muted)
    else:
        # Source-derived cards and optional model-selected safe layouts.
        layout = kind if kind in {"sequence","comparison","cycle"} else "concept_map"
        count = len(labels)
        for i,label in enumerate(labels):
            if layout == "cycle":
                angle = i*math.tau/count - math.pi/2
                x,y = 450+230*math.cos(angle)-105,365+120*math.sin(angle)-45
            elif layout == "comparison":
                x,y = 65+(i%2)*390,180+(i//2)*125
            else:
                x,y = 75+(i%3)*260,220+(i//3)*170
            if i and layout == "sequence":
                arrow((last[0]+210,last[1]+45),(x,y+45))
            draw.rounded_rectangle((x,y,x+210,y+100),radius=16,fill="#213b58",outline=yellow if i == active else blue,width=4)
            text(x+14,y+15,label,width=182,lines=2)
            last = (x,y)
        if scene.equation:
            text(65, 530, scene.equation, width=790, lines=1, color=yellow)
    # Reserve a clear caption region; do not duplicate or replace WebVTT cues.
    text(45, 620, "Illustrative visual" if plan.provenance_kind == "AI_ENRICHED" else "Source excerpt overview",
         width=1100, lines=1, color=muted)
    draw.rectangle((28,694,28+int(1224*max(0,min(1,ratio))),700),fill=blue)
    return image
