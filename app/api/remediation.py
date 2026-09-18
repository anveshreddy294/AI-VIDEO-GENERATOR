"""Step 4 API — Remediation Verification & Re-Testing Loop.

Endpoints:
- POST /remediation/start  → Generate a targeted 1-2 question verification session for a concept
- POST /remediation/submit → Grade verification answers, update mastery to MASTERED or trigger kill switch
"""

from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..services.assessment.schemas import AnswerSubmission, ProfileSummary, SafeQuestion
from ..services.remediation.engine import (
    create_remediation_session,
    evaluate_remediation_submission,
)

router = APIRouter(prefix="/remediation", tags=["Step 4 — Remediation & Re-Testing"])


class RemediationStartRequest(BaseModel):
    """Request payload to initiate a remediation verification check."""
    student_id: str = Field(description="The student identifier")
    source_id: str = Field(description="The source document/material identifier")
    concept_id: str = Field(description="The concept being verified")
    count: int = Field(default=1, ge=1, le=5, description="Number of verification questions (1-2 recommended)")


class RemediationStartResponse(BaseModel):
    """Response containing sanitized verification questions and session metadata."""
    session_id: str
    student_id: str
    source_id: str
    concept_id: str
    questions: List[SafeQuestion]
    status: str = "READY"


class RemediationSubmitRequest(BaseModel):
    """Request payload to submit answers for remediation verification."""
    session_id: str = Field(description="The remediation session ID")
    student_id: str = Field(description="The student identifier")
    concept_id: str = Field(description="The concept identifier")
    answers: List[AnswerSubmission] = Field(description="List of selected answer options")


class RemediationSubmitResponse(BaseModel):
    """Response with grading, mastery transition, and updated learning profile."""
    session_id: str
    student_id: str
    concept_id: str
    concept_name: str
    passed: bool
    score: int
    total: int
    percentage: float
    previous_status: str
    new_status: str
    message: str
    explanations: List[str]
    profile_summary: ProfileSummary


@router.post("/start", response_model=RemediationStartResponse)
def start_remediation(req: RemediationStartRequest) -> RemediationStartResponse:
    """Initialize a targeted verification re-assessment for a concept."""
    try:
        session, safe_questions = create_remediation_session(
            student_id=req.student_id,
            source_id=req.source_id,
            concept_id=req.concept_id,
            count=req.count,
        )
        return RemediationStartResponse(
            session_id=session.session_id,
            student_id=session.student_id,
            source_id=session.source_id,
            concept_id=req.concept_id,
            questions=safe_questions,
            status=session.status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create remediation session: {str(e)}")


@router.post("/submit", response_model=RemediationSubmitResponse)
def submit_remediation(req: RemediationSubmitRequest) -> RemediationSubmitResponse:
    """Submit student answers for the remediation verification check and update profile."""
    try:
        result = evaluate_remediation_submission(
            session_id=req.session_id,
            student_id=req.student_id,
            concept_id=req.concept_id,
            answers=req.answers,
        )
        return RemediationSubmitResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to evaluate remediation submission: {str(e)}")
