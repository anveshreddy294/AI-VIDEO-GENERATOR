"""Tests for BUG-003: FFmpeg Process Real Timeout and Zombie Cleanup."""

import asyncio
import sys
from pathlib import Path
import pytest

from app.services.video.video_compositor import (
    FFmpegTimeoutError,
    composite_remedial_video,
    run_subprocess_bounded,
)


def test_subprocess_timeout_terminates_and_reaps(tmp_path):
    async def _test():
        output_file = tmp_path / "partial_output.mp4"
        output_file.write_text("partial corrupt content")

        # Launch python command that sleeps for 10 seconds
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]

        loop = asyncio.get_running_loop()
        start = loop.time()
        with pytest.raises(FFmpegTimeoutError) as exc_info:
            await run_subprocess_bounded(
                cmd,
                timeout=0.3,
                output_path=output_file,
                log_prefix="[test_timeout]",
            )
        elapsed = loop.time() - start

        # Should have timed out within ~0.5 seconds, not 10 seconds
        assert elapsed < 2.0
        assert "timed out" in str(exc_info.value).lower()

        # Incomplete output file must have been deleted
        assert not output_file.exists()

    asyncio.run(_test())


def test_subprocess_normal_completion(tmp_path):
    async def _test():
        output_file = tmp_path / "valid.txt"
        cmd = [sys.executable, "-c", "import sys; sys.exit(0)"]

        returncode, stdout, stderr = await run_subprocess_bounded(
            cmd,
            timeout=2.0,
            output_path=output_file,
        )
        assert returncode == 0

    asyncio.run(_test())


def test_composite_remedial_video_respects_timeout(tmp_path, monkeypatch):
    async def _test():
        video = tmp_path / "in.mp4"
        audio = tmp_path / "in.wav"
        out = tmp_path / "out.mp4"
        video.write_bytes(b"dummy video")
        audio.write_bytes(b"dummy audio")

        # Mock ffmpeg binary to python executable
        import shutil
        monkeypatch.setattr(shutil, "which", lambda name: sys.executable if name == "ffmpeg" else None)

        # Monkeypatch run_subprocess_bounded to simulate timeout
        async def mock_run_timeout(*args, **kwargs):
            raise FFmpegTimeoutError("FFmpeg timed out")

        from app.services.video import video_compositor
        monkeypatch.setattr(video_compositor, "run_subprocess_bounded", mock_run_timeout)

        with pytest.raises(FFmpegTimeoutError):
            await composite_remedial_video(
                video_mp4=video,
                audio_wav=audio,
                output_mp4=out,
                timeout=0.1,
            )

    asyncio.run(_test())
