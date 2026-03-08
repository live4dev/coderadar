import pytest
from app.services.identity.normalizer import normalize_identity


def test_latin_full_name():
    r = normalize_identity("Dmitry Ivanov")
    assert r.canonical_username == "d_ivanov"


def test_cyrillic_full_name():
    r = normalize_identity("Дмитрий Иванов")
    assert r.canonical_username == "d_ivanov"


def test_email_hint_standard():
    r = normalize_identity("D Ivanov", "d.ivanov@company.com")
    assert r.canonical_username == "d_ivanov"
    assert r.source == "email"


def test_email_local_part_canonical():
    r = normalize_identity("unknown", "a_petrov@example.com")
    assert r.canonical_username == "a_petrov"


def test_manual_override_by_name():
    overrides = {"dmitry ivanov": "d_ivanov_override"}
    r = normalize_identity("Dmitry Ivanov", overrides=overrides)
    assert r.canonical_username == "d_ivanov_override"
    assert r.source == "override"


def test_manual_override_by_email():
    overrides = {"d.ivanov@corp.com": "d_ivanov"}
    r = normalize_identity("Somebody", "d.ivanov@corp.com", overrides=overrides)
    assert r.canonical_username == "d_ivanov"


def test_single_token_name():
    r = normalize_identity("ghostdev")
    assert r.canonical_username == "ghostdev"
    assert r.is_ambiguous is True


def test_confidence_full_name_latin():
    r = normalize_identity("Anna Sokolova")
    assert r.confidence >= 0.8


def test_mixed_case():
    r = normalize_identity("IVAN PETROV")
    assert r.canonical_username == "i_petrov"
