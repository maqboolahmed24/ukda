from __future__ import annotations

import pytest

from app.documents.service import DocumentService, DocumentValidationError


def test_redaction_action_type_defaults_to_mask() -> None:
    assert DocumentService._normalize_redaction_action_type(None) == "MASK"
    assert DocumentService._normalize_redaction_action_type("mask") == "MASK"


@pytest.mark.parametrize("action_type", ["PSEUDONYMIZE", "GENERALIZE"])
def test_redaction_action_type_accepts_phase7_actions(action_type: str) -> None:
    assert DocumentService._normalize_redaction_action_type(action_type) == action_type


def test_redaction_action_type_rejects_unknown_values() -> None:
    with pytest.raises(DocumentValidationError, match="MASK, PSEUDONYMIZE, or GENERALIZE"):
        DocumentService._normalize_redaction_action_type("REDACT")
