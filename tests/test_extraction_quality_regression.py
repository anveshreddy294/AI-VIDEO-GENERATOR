"""Regression test suite for extraction quality validator (Phase 1 & Phase 2).

Verifies that legitimate educational content containing layout formatting, whitespace runs,
ASCII tables, and separator characters is accepted, while genuine extraction corruption,
encoding errors, and OCR garbage fail closed.
"""

from app.services.schemas import ContentUnit
from app.services.validator import validate_extraction_quality


# =========================================================================
# VALID CASES (Must PASS)
# =========================================================================

def test_valid_case_1_standard_educational_statement():
    """1. Standard physics statement."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="Newton's Second Law states that force equals mass times acceleration.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_case_2_long_whitespace_runs_and_indentation():
    """2. Text with long whitespace runs and indentation."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="Heading\n\n                    Body text describing angular momentum and torque in rotational dynamics.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_case_3_dash_separators_in_educational_document():
    """3. Long dash separator line inside an otherwise legitimate document."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text=(
            "----------------------------------------\n"
            "Section 2: Thermodynamics\n"
            "The first law of thermodynamics relates heat and work.\n"
            "----------------------------------------"
        ),
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_case_4_underscore_separators_in_notes():
    """4. Long underscore line inside legitimate student notes."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text=(
            "________________________________________\n"
            "Topic: Chemical Equilibrium and Le Chatelier's Principle\n"
            "When a system at equilibrium is disturbed, the system shifts.\n"
            "________________________________________"
        ),
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_case_5_dotted_table_leaders():
    """5. Dotted table of contents line."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text=(
            "Table of Contents\n"
            "Chapter 1........................Page 5: Kinematics and Motion\n"
            "Chapter 2........................Page 22: Dynamics and Forces\n"
        ),
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_case_6_ascii_table_formatting():
    """6. ASCII / engineering table formatting."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text=(
            "+------------------+------------------+------------------+\n"
            "| Parameter        | Symbol           | SI Unit          |\n"
            "+==================+==================+==================+\n"
            "| Electric Field   | E                | Volt per meter   |\n"
            "| Magnetic Flux    | Phi              | Weber            |\n"
            "+------------------+------------------+------------------+\n"
        ),
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_case_7_short_engineering_note_with_formulas():
    """7. Short engineering note containing formulas and symbols."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="Ohm's law relates voltage, current, and resistance: V = I * R, where R is measured in ohms.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


def test_valid_repeated_word_coooooool():
    """Ordinary repeated character in words (e.g. 'coooooool') must not fail."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="This experiment demonstrates a coooooool phenomenon where liquid nitrogen instantly freezes water droplets.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is True
    assert status == "PASSED"


# =========================================================================
# INVALID CASES (Must Fail Closed with EXTRACTION_INSUFFICIENT / FAILED)
# =========================================================================

def test_invalid_case_8_unicode_replacement_corruption():
    """8. Unicode replacement character corruption."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="pdf",
        text="\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd\ufffd Physics text corrupted",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"


def test_invalid_case_9_multiple_nul_bytes():
    """9. Multiple binary NUL bytes indicating stream corruption."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="pdf",
        text="PDF_STREAM_ERROR \x00\x00\x00\x00\x00 corrupted binary chunk",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"


def test_invalid_case_10_extreme_repeated_alphabetic_garbage():
    """10. Extreme repeated alphabetic garbage."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa Physics note on velocity and acceleration.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"


def test_invalid_case_11_extreme_repeated_numeric_garbage():
    """11. Extreme repeated numeric garbage."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="1111111111111111111111111111111111111111 Physics lecture notes on kinematics and vectors.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"


def test_invalid_case_12_metadata_only_input():
    """12. Metadata-only input (file paths, mime types, filenames)."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="pdf",
        text="lecture_notes.pdf application/pdf 2026-10-05 storage/runtime/uploads/lecture_notes.pdf",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"


def test_invalid_case_13_unresolved_image_placeholder():
    """13. Unresolved synthetic image placeholder."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="image",
        text="[IMAGE: diagram.png]\nImage asset for 'diagram'. Visual study reference material from uploaded media.",
        visual_description="Image asset for 'diagram'. Visual study reference material from uploaded media.",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"


def test_invalid_case_14_repetitive_token_gibberish():
    """14. Repetitive token gibberish."""
    unit = ContentUnit(
        source_id="src_1",
        asset_id="ast_1",
        modality="txt",
        text="asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf asdf",
    )
    is_valid, status, reason = validate_extraction_quality([unit])
    assert is_valid is False
    assert status == "EXTRACTION_INSUFFICIENT"
