"""Two real worker processes, forced termination and recovery in a fresh process."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from app.core.config import settings
from app.services import educational_content as ec
from tests.test_source_supabase import context, OWNER
from tests.test_video_generation_foundation import service
from tests.test_educational_video_enhancements import completed


def test_simultaneous_regeneration_survives_real_process_termination(service,tmp_path):
    lesson,artifact = completed(service)
    original_bytes = Path(artifact.video_path).read_bytes()
    plan = lesson.video_generations["generation-a"].plan
    plan_path = tmp_path/"plan.json"
    plan_path.write_text(plan.model_dump_json(),encoding="utf-8")
    gate = tmp_path/"go"
    env = {**os.environ,"PYTHON_DOTENV_DISABLED":"1","RUNTIME_DIR":str(settings.runtime_dir)}
    def command(mode,marker):
        return [sys.executable,"-B","-m","tests.video_process_worker",mode,str(ec.LESSONS_DIR),
                str(OWNER),lesson.lesson_id,str(marker),str(plan_path),str(gate)]
    markers = [tmp_path/f"worker-{i}.json" for i in range(2)]
    processes = [subprocess.Popen(command("start",marker),env=env,stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE,text=True) for marker in markers]
    try:
        gate.write_text("start")
        deadline = time.monotonic()+25
        while not all(marker.exists() for marker in markers):
            assert time.monotonic() < deadline, "Isolated workers did not start"
            for process,marker in zip(processes,markers):
                if process.poll() is not None and not marker.exists():
                    stdout,stderr = process.communicate()
                    raise AssertionError(f"Child worker failed: {stdout} {stderr}")
            time.sleep(.03)
        results = [json.loads(marker.read_text()) for marker in markers]
        assert results[0]["job_id"] == results[1]["job_id"]
        job_id = results[0]["job_id"]
        active = service.get_lesson(lesson.lesson_id)
        assert active.video["status"] == "RENDERING"
        assert len(active.video_generations) == 2
        assert active.video_generations["generation-a"].status == "COMPLETED"
        assert Path(artifact.video_path).read_bytes() == original_bytes
    finally:
        # Terminate only the two disposable processes launched by this test.
        for process in processes:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
    marker = tmp_path/"restarted.json"
    subprocess.run(command("recover",marker),env=env,capture_output=True,text=True,timeout=25,check=True)
    recovered = ec.EducationalLesson.model_validate_json(marker.read_text(encoding="utf-8"))
    assert recovered.video["job_id"] == job_id
    assert recovered.video["status"] == "FAILED"
    assert recovered.video["error_code"] == "VIDEO_JOB_INTERRUPTED"
    assert recovered.video_generations[job_id].status == "FAILED"
    assert recovered.video_generations[job_id].completed_at
    assert recovered.video_generations[job_id].plan == active.video_generations[job_id].plan
    assert recovered.video_generations[job_id].prior_job_id == "generation-a"
    assert recovered.video_generations["generation-a"].status == "COMPLETED"
    assert Path(artifact.video_path).read_bytes() == original_bytes
