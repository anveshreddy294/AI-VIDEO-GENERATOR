"""Run the production Steps 1–2 flow with Ollama text reasoning.

Local embeddings and durable Qdrant storage are used. This demo
submits simulated answers and persists a session, profile, and video blueprint.
"""
import asyncio
import io

from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.config import settings
from app.api.upload import upload_file
from app.api.assessment import submit_assessment
from app.services.assessment.schemas import AnswerSubmission, StudentSubmission
from app.services.assessment.session_store import load_session


DEFAULT_TOPIC_TEXT = """Thermodynamics and Heat Transfer

Chapter 1: Thermal Foundations
Section 1.1: Thermal Equilibrium and Temperature
The Zeroth Law of Thermodynamics establishes temperature as a fundamental state property. It states that if two thermodynamic systems are each in thermal equilibrium with a third system, then they are in thermal equilibrium with each other. Temperature is the physical quantity that determines whether systems are in thermal equilibrium. When two objects with different temperatures are brought into contact, thermal energy flows spontaneously from the higher temperature object to the lower temperature object until equilibrium is achieved.

Section 1.2: Conservation of Thermal Energy
The First Law of Thermodynamics is the principle of conservation of energy applied to thermodynamic systems. It states that the change in internal energy (Delta U) of a closed system is equal to the net heat added to the system (Q) minus the work done by the system on its surroundings (W): Delta U = Q - W. Internal energy is a state function representing the microscopic kinetic and potential energy of the molecules. Heat and work are path-dependent mechanisms of energy transfer across system boundaries.

Chapter 2: Entropy and Cycles
Section 2.1: The Second Law and Entropy
The Second Law of Thermodynamics states that the total entropy of an isolated system always increases over time in any spontaneous natural process. Entropy is a measure of the molecular disorder or unavailable energy in a system. Heat cannot spontaneously flow from a colder body to a hotter body without external work being done on the system. All real processes are irreversible, generating positive entropy production.

Section 2.2: Heat Engines and the Carnot Efficiency
A heat engine absorbs heat from a high-temperature thermal reservoir, converts a fraction of it into mechanical work, and expels the remainder to a low-temperature reservoir. The Carnot cycle defines the theoretical upper limit for the thermal efficiency of any heat engine operating between two temperature reservoirs: eta = 1 - (T_cold / T_hot), where temperatures are expressed in Kelvin. No real heat engine can achieve higher efficiency than a reversible Carnot engine operating between the same two temperatures.
"""


async def run_demo():
    if settings.llm_provider != "ollama":
        raise RuntimeError("This runner requires LLM_PROVIDER=ollama")
    print(f"Text reasoning: Ollama {settings.ollama_model}; embeddings: {settings.embedding_model}; storage: Qdrant")
    upload = UploadFile(file=io.BytesIO(DEFAULT_TOPIC_TEXT.encode("utf-8")),
        filename="thermodynamics_topic.txt", headers=Headers({"content-type": "text/plain"}))
    try:
        result = await upload_file(file=upload, auto_start_assessment=True,
            student_id="student_thermo_learner", max_questions=3)
    finally:
        await upload.close()
    quiz = result.get("assessment") or {}
    if quiz.get("error") or not quiz.get("questions"):
        raise RuntimeError(quiz.get("error") or "No assessment questions generated")
    session = load_session(quiz["session_id"])
    if session is None:
        raise RuntimeError("Generated session was not persisted")
    print(f"Source {result['source_id']}: {result['chunks_synced']} verified stored chunks")
    print(f"Generated {len(session.questions)} questions (requested 3)")
    # Backend-only demo: deliberately answer the second question incorrectly.
    answers = [AnswerSubmission(question_id=q.question_id,
        selected_index=(q.correct_index + 1) % 4 if i == 1 else q.correct_index)
        for i, q in enumerate(session.questions)]
    graded = await asyncio.to_thread(submit_assessment,
        StudentSubmission(session_id=session.session_id, answers=answers))
    print(f"Persisted assessment {graded.session_id}: {graded.score}/{graded.total}")
    print(f"Video blueprint: {graded.video_target_matrix.decision}")
    return graded


def main():
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
