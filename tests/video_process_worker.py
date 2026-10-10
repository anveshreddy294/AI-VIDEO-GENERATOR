"""Isolated test child process; never connects to providers or the real server."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS
from uuid import UUID

from app.services import educational_content as ec
from app.services.video.scene_schema import VideoPlan


async def main():
    mode, directory, user_id, lesson_id, marker, plan_path, gate = sys.argv[1:]
    ec.LESSONS_DIR = Path(directory)
    user = UUID(user_id)
    service = ec.EducationalContentService(NS(user=NS(user_id=user)))
    if mode == "recover":
        lesson = service.get_lesson(lesson_id)
        Path(marker).write_text(lesson.model_dump_json(),encoding="utf-8")
        return
    while not Path(gate).exists():
        await asyncio.sleep(.02)
    async def execute(lesson_id,user_id,plan,job_id):
        lesson = ec.get_educational_lesson(user_id,lesson_id)
        lesson.video.update(status="RENDERING",stage="RENDERING",progress=50)
        ec.save_educational_lesson(lesson)
        # The test intentionally kills this process while its real job lock is held.
        await asyncio.Event().wait()
    service._execute_video_pipeline = execute
    lesson = ec.get_educational_lesson(user,lesson_id)
    result = service.start_video_job(lesson,regenerate=True,
                                    plan=VideoPlan.model_validate_json(Path(plan_path).read_text()))
    await asyncio.sleep(.05)
    Path(marker).write_text(json.dumps(result),encoding="utf-8")
    if ec._video_tasks:
        await asyncio.gather(*ec._video_tasks)


if __name__ == "__main__":
    asyncio.run(main())
