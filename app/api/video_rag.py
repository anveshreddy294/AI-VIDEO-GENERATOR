"""Video RAG & Timestamp Q&A API.

Endpoints:
- POST /video/rag/ask → Ask a contextual question about a video lesson with timestamp synchronization
"""

import logging
from fastapi import APIRouter, HTTPException

from ..services.video_rag.engine import answer_video_question
from ..services.video_rag.schemas import VideoQARequest, VideoQAResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/video/rag", tags=["Video RAG & Q&A"])


@router.post("/ask", response_model=VideoQAResponse)
def ask_video_question(req: VideoQARequest) -> VideoQAResponse:
    """Answer a student's question grounded in the video's active scene and source material."""
    try:
        response = answer_video_question(
            video_id=req.video_id,
            question=req.question,
            timestamp=req.timestamp,
            student_id=req.student_id,
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("Error in video RAG endpoint: %s", e)
        raise HTTPException(status_code=500, detail=f"Failed to process video question: {str(e)}")
