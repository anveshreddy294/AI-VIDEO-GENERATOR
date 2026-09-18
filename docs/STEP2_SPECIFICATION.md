# VisualAI — Step 2 Architecture Specification: Diagnostic Assessment & Student Knowledge Profiling

## Executive Overview & Architectural Philosophy

Step 1 transformed multimodal raw study material (PDF, Image, TXT, Video) into a structured, dual-traceable knowledge base of **ContentUnits**, **Knowledge Graphs**, and **Layer A Qdrant Chunks**.

**Step 2 does NOT immediately jump to personalized video generation or arbitrary quiz generation.**

Instead, Step 2 acts as the **Diagnostic Measurement & Knowledge Profiling Bridge**. Its primary responsibility is to answer:
> *"What does this specific student already know, and what are their specific conceptual and prerequisite gaps within this uploaded material?"*

The primary artifact produced by Step 2 is the **Student Learning Profile**. This profile contains granular concept-level mastery scores and prerequisite gap analysis that will later feed the **Learning Agent (Step 3)** and **Dynamic RAG Engine (Step 4)**.

---

## 1. End-to-End System Integration Flow

```
                                  STEP 1: KNOWLEDGE PREPARATION
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ STUDENT UPLOAD (PDF / Image / TXT / Video)                                                  │
│      │                                                                                      │
│      ▼                                                                                      │
│ Source Identity (source_id, asset_id, file_hash, version)                                   │
│      │                                                                                      │
│      ▼                                                                                      │
│ Extraction & Normalization ──► ContentUnits (page, timestamp, bbox, visual_description)    │
│      │                                                                                      │
│      ▼                                                                                      │
│ Structure & Concept Engine ──► KnowledgeGraph (concept nodes & prerequisite links)          │
│                            ──► TopicBlueprint (derived view)                                │
│      │                                                                                      │
│      ▼                                                                                      │
│ Semantic Chunker           ──► RichChunks (layer="A", concept_ids, content_ids, page/time)  │
│      │                                                                                      │
│      ▼                                                                                      │
│ Qdrant Vector Store        ──► Indexed Layer A Embeddings                                   │
│      │                                                                                      │
│      ▼                                                                                      │
│ Quality Validation Gateway ──► Source Status = READY                                        │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
                                               │ Connection Bridge:
                                               │ • source_id (e.g., SRC_feec0cfbc285)
                                               │ • asset_id  (e.g., AST_c2f2ea672346)
                                               │ • student_id (e.g., STU_001)
                                               ▼
                              STEP 2: DIAGNOSTIC ASSESSMENT & PROFILING
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1. Step 1 Artifact Loader (Repository)                                                      │
│    Verifies source_id status == READY.                                                      │
│    Loads TopicBlueprint, KnowledgeGraph, and ContentUnits.                                  │
│      │                                                                                      │
│      ▼                                                                                      │
│ 2. Assessment Planner & Concept Selector                                                    │
│    Inspects KnowledgeGraph prerequisite trees & depth levels.                               │
│    Selects 10–15 representative concepts (foundational, intermediate, advanced).            │
│      │                                                                                      │
│      ▼                                                                                      │
│ 3. Qdrant Grounded Context Retriever                                                        │
│    For each selected concept, queries Qdrant Layer A using concept filters & vector query.  │
│    Retrieves exact RichChunks with source provenance (chunk_ids, pages, timestamps).        │
│      │                                                                                      │
│      ▼                                                                                      │
│ 4. Grounded Question Generator (Gemini LLM)                                                 │
│    Prompts Gemini with ONLY the retrieved authoritative chunks.                              │
│    Forces structured JSON output (questions, options, correct_answer, concept_ids).         │
│      │                                                                                      │
│      ▼                                                                                      │
│ 5. Question Validation Gateway                                                              │
│    Enforces 7 quality checks: concept existence, chunk existence, schema validity,           │
│    single correct answer, provenance integrity, non-duplication, zero hallucination.        │
│      │                                                                                      │
│      ▼                                                                                      │
│ 6. Assessment Delivery & Student Submission                                                 │
│    Student takes assessment (answers questions without seeing correct answer keys).           │
│      │                                                                                      │
│      ▼                                                                                      │
│ 7. Answer Evaluator & Concept Mastery Engine                                                │
│    Evaluates answers, updates concept attempt history, calculates mastery percentages (0-1). │
│    Maps mastery back to KnowledgeGraph prerequisite chains.                                 │
│      │                                                                                      │
│      ▼                                                                                      │
│ 8. Student Learning Profile Generation & Persistence                                        │
│    Saves persistent JSON profile under storage/assessments/learning_profiles/STU_xxx/      │
└──────────────────────────────────────────────┬──────────────────────────────────────────────┘
                                               │
                                               │ Consumed by downstream steps:
                                               │ • student_id, source_id
                                               │ • weak_concepts & prerequisite_gaps
                                               ▼
                              STEP 3: LEARNING AGENT & STEP 4: DYNAMIC RAG
```

---

## 2. Step 1 to Step 2 Connection Mechanism

Step 2 connects to Step 1 **exclusively through source identifiers (`source_id`, `asset_id`)**. 

Step 2 **NEVER** re-parses or re-reads the raw PDF/Video file. Instead, it consumes the normalized, structured artifacts produced by Step 1:

| Step 1 Artifact | Location / Storage | How Step 2 Uses It |
|---|---|---|
| **Source Record** | `storage/registry/sources_index.json` | Validates `status == "READY"` and checks file metadata/version. |
| **TopicBlueprint** | `storage/registry/{source_id}/topic_blueprint.json` | Provides high-level topic name, overall difficulty, and overview. |
| **KnowledgeGraph** | `storage/registry/{source_id}/knowledge_graph.json` | Provides concept nodes, definitions, and prerequisite dependency graphs. |
| **ContentUnits** | `storage/registry/{source_id}/content_units.json` | Provides page numbers, video timestamps, visual descriptions, line bounds. |
| **RichChunks (Qdrant)** | Qdrant `visualai_layer_a` collection | Provides verbatim authoritative text chunks for grounded question generation. |

---

## 3. Step 2 Data Schemas & Data Contracts

### 3.1 `AssessmentRequest`
Client request to generate a diagnostic assessment:
```json
{
  "source_id": "SRC_feec0cfbc285",
  "student_id": "STU_001",
  "assessment_type": "diagnostic",
  "question_count": 10
}
```

### 3.2 `AssessmentQuestion` (Backend Internal Representation with Provenance)
```json
{
  "question_id": "Q_001",
  "question": "What is the primary purpose of database sharding?",
  "question_type": "mcq",
  "difficulty": "easy",
  "options": [
    "To duplicate data across multiple geographical regions",
    "To horizontally partition data across multiple database instances",
    "To cache frequent query responses in memory",
    "To encrypt data at rest"
  ],
  "correct_answer": "To horizontally partition data across multiple database instances",
  "concept_ids": ["CONCEPT_SHARDING"],
  "prerequisite_concept_ids": ["CONCEPT_PARTITIONING"],
  "source_id": "SRC_feec0cfbc285",
  "asset_id": "AST_c2f2ea672346",
  "chunk_ids": ["CHUNK_51a9e012"],
  "content_ids": ["CU_048_01", "CU_048_02"],
  "page_start": 48,
  "page_end": 49,
  "timestamp_start": null,
  "timestamp_end": null
}
```

### 3.3 `AssessmentResponse` (Client-Facing Delivery Schema)
The student UI receives questions **WITHOUT** revealing `correct_answer`:
```json
{
  "assessment_id": "ASSIGN_9f82a10b",
  "title": "System Design — Diagnostic Assessment",
  "student_id": "STU_001",
  "source_id": "SRC_feec0cfbc285",
  "question_count": 10,
  "questions": [
    {
      "question_id": "Q_001",
      "question": "What is the primary purpose of database sharding?",
      "question_type": "mcq",
      "options": [
        "To duplicate data across multiple geographical regions",
        "To horizontally partition data across multiple database instances",
        "To cache frequent query responses in memory",
        "To encrypt data at rest"
      ]
    }
  ]
}
```

### 3.4 `AssessmentSubmission`
Submitted student answers:
```json
{
  "student_id": "STU_001",
  "assessment_id": "ASSIGN_9f82a10b",
  "answers": [
    {
      "question_id": "Q_001",
      "selected_answer": "To horizontally partition data across multiple database instances",
      "time_taken_seconds": 24
    }
  ]
}
```

### 3.5 `StudentLearningProfile` (The Final Core Artifact of Step 2)
```json
{
  "student_id": "STU_001",
  "source_id": "SRC_feec0cfbc285",
  "overall_score": 0.40,
  "last_updated": "2026-09-16T19:00:00Z",
  "concept_mastery": {
    "CONCEPT_HTTP": 0.90,
    "CONCEPT_DNS_RESOLUTION": 0.85,
    "CONCEPT_LOAD_BALANCERS": 0.40,
    "CONCEPT_PARTITIONING": 0.30,
    "CONCEPT_SHARDING": 0.20,
    "CONCEPT_APACHE_KAFKA": 0.10
  },
  "strong_concepts": ["CONCEPT_HTTP", "CONCEPT_DNS_RESOLUTION"],
  "weak_concepts": ["CONCEPT_LOAD_BALANCERS", "CONCEPT_PARTITIONING", "CONCEPT_SHARDING", "CONCEPT_APACHE_KAFKA"],
  "prerequisite_gaps": [
    {
      "target_concept": "CONCEPT_SHARDING",
      "missing_prerequisite": "CONCEPT_PARTITIONING",
      "prerequisite_mastery": 0.30
    }
  ],
  "history": [
    {
      "assessment_id": "ASSIGN_9f82a10b",
      "score": 0.40,
      "date": "2026-09-16T19:00:00Z"
    }
  ]
}
```

---

## 4. Detailed Component Specifications for Step 2

### Component 1: Step 1 Artifact Loader (`repository.py`)
- **Function**: Loads persisted registry records, `TopicBlueprint`, `KnowledgeGraph`, and `ContentUnits` for a given `source_id`.
- **Guardrail**: If `source_record.status != "READY"`, rejects the request with HTTP 400 ("Source material is not ready for assessment generation").

### Component 2: Assessment Planner & Concept Selector (`planner.py`, `concept_selector.py`)
- **Function**: Selects 10–15 representative concepts out of all concepts in the `KnowledgeGraph`.
- **Selection Strategy**:
  1. Traverses the `KnowledgeGraph` dependency DAG.
  2. Identifies root prerequisite concepts (Foundational), intermediate concepts, and leaf concepts (Advanced).
  3. Ensures proportional representation (e.g., 40% Foundational, 40% Intermediate, 20% Advanced).
  4. Guarantees that if an advanced concept is selected, its prerequisite concepts are also included to diagnose root causes of failure.

### Component 3: Qdrant Grounded Context Retriever (`retriever.py`)
- **Function**: Fetches authoritative chunks from Qdrant for each selected concept.
- **Query Strategy**: Performs a filtered vector search on Qdrant `visualai_layer_a` collection matching `source_id` and target `concept_id`.
- **Output**: Returns relevant `RichChunk` objects containing verbatim source text, `chunk_ids`, `content_ids`, page numbers, and timestamps.

### Component 4: Grounded Question Generator (`generator.py`, `prompts.py`)
- **Function**: Prompts Gemini LLM with strict grounding constraints.
- **Strict Prompting Rules**:
  - *"Generate questions using ONLY the supplied authoritative context."*
  - *"Do not introduce external facts or unmentioned terminology."*
  - *"Respond with strict JSON matching the schema."*
- **Provenance Injection**: The generator injects the retrieved `source_id`, `chunk_ids`, `content_ids`, `page_start`, `page_end`, and `timestamp_start/end` into the generated question object.

### Component 5: Question Validation Gateway (`validator.py`)
- **Function**: Runs multi-checkpoint validation before locking the assignment:
  1. **Concept Integrity**: Every question's `concept_ids` must exist in the `KnowledgeGraph`.
  2. **Provenance Integrity**: `source_id`, `chunk_ids`, and `content_ids` must exist in Step 1 registry/Qdrant.
  3. **Option Integrity**: MCQ must have exactly 4 distinct options and 1 exact matching correct answer.
  4. **Grounding Check**: Verifies question facts against the retrieved chunk text.
  5. **Non-Duplication Check**: Ensures questions are semantically distinct across the assessment.

### Component 6: Answer Evaluator & Mastery Engine (`evaluator.py`, `mastery.py`)
- **Function**: Evaluates student responses and calculates concept mastery.
- **Mastery Calculation Formula**:
  $$\text{Mastery}(c) = \frac{\text{Correct Attempts}(c)}{\text{Total Attempts}(c)} \times \text{Difficulty Weight}$$
- **Prerequisite Gap Detection**: If a student fails a target concept (e.g., `CONCEPT_SHARDING`), the engine checks the `KnowledgeGraph` for its prerequisites (e.g., `CONCEPT_PARTITIONING`). If the prerequisite mastery is also low ($\le 0.50$), it flags a **Prerequisite Gap**.

### Component 7: Learning Profile Storage (`repository.py`)
- **Function**: Persists student learning profiles under `storage/assessments/learning_profiles/{student_id}/{source_id}.json`.

---

## 5. API Endpoints Specification

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/assessment/create` | Accepts `source_id` & `student_id`, runs Planner + Retriever + Generator + Validator, stores assessment, returns `assessment_id`. |
| `GET` | `/assessment/{assessment_id}` | Returns student-facing questions (without answers). |
| `POST` | `/assessment/{assessment_id}/submit` | Accepts student answers, evaluates correct/incorrect, updates concept mastery, persists `StudentLearningProfile`. |
| `GET` | `/assessment/{assessment_id}/result` | Returns evaluation summary, score breakdown, and updated concept strengths/weaknesses. |
| `GET` | `/student/{student_id}/learning-profile/{source_id}` | Retrieves the persistent `StudentLearningProfile`. |

---

## 6. Connection to Downstream Steps (Step 3 & Step 4)

Once Step 2 is complete, the resulting `StudentLearningProfile` cleanly connects to subsequent pipeline phases:

```
┌──────────────────────────────┐
│   StudentLearningProfile     │
│  - Weak Concepts: [Sharding] │
│  - Gap: [Partitioning]       │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  STEP 3: LEARNING AGENT      │
│  "Student needs Partitioning │
│   before learning Sharding"  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│  STEP 4: DYNAMIC RAG         │
│  Retrieves Qdrant Layer A    │
│  chunks specifically for     │
│  Partitioning & Sharding     │
└──────────────┬───────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
┌─────────────┐ ┌──────────────┐
│ Target Quiz │ │ Personalized │
│ Generator   │ │ Video Lesson │
└─────────────┘ └──────────────┘
```

---

## 7. Implementation Blueprint (Module File Structure)

When implementation begins, the new `app/services/assessment/` module will be structured as follows:

```
AI-VIDEO-GENERATOR/
├── app/
│   ├── api/
│   │   ├── upload.py (Step 1 - Complete)
│   │   └── assessment.py (Step 2 API Routes)
│   └── services/
│       └── assessment/
│           ├── __init__.py
│           ├── schemas.py       # Pydantic models for Requests, Questions, Profiles
│           ├── repository.py    # Step 1 artifact loader & Profile persistence
│           ├── planner.py       # Assessment Planner & Concept Selector
│           ├── retriever.py     # Grounded Qdrant Chunk Retriever
│           ├── generator.py     # Gemini Grounded Question Generator
│           ├── prompts.py       # Strict LLM prompts for question generation
│           ├── validator.py     # Question Quality & Provenance Validator
│           ├── evaluator.py     # Answer Evaluator
│           └── mastery.py       # Concept Mastery & Prerequisite Gap Calculator
├── storage/
│   └── assessments/
│       ├── assignments/         # Generated diagnostic assessments
│       ├── submissions/         # Student answer submissions
│       └── learning_profiles/   # Persistent Student Learning Profiles
└── test_step2.py                # End-to-end verification script for Step 2
```
