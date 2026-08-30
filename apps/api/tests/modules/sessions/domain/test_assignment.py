import pytest

from app.modules.sessions.domain.errors import InvalidJustification
from app.modules.sessions.domain.models import normalize_justification


def test_normalize_justification_strips_a_valid_reason() -> None:
    assert normalize_justification("  Confirmado pelo síndico  ") == (
        "Confirmado pelo síndico"
    )


@pytest.mark.parametrize("value", ["", "   ", "\n\t"])
def test_normalize_justification_rejects_blank_reason(value: str) -> None:
    with pytest.raises(InvalidJustification):
        normalize_justification(value)
