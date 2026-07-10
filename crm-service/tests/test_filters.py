"""Тесты построения SQL-фильтра (чистая функция build_where)."""
from app.db import build_where


def test_empty_filters():
    where, params = build_where({})
    assert where == "TRUE"
    assert params == []


def test_created_range_uses_positional_params():
    where, params = build_where({"created_from": "2026-01-01", "created_to": "2026-12-31"})
    assert "created_at >= $1" in where
    assert "created_at <= $2" in where
    assert len(params) == 2  # значения ушли в параметры, не в текст SQL


def test_has_email_true_is_static_sql():
    where, params = build_where({"has_email": True})
    assert "email IS NOT NULL AND email <> ''" in where
    assert params == []


def test_has_phone_false():
    where, params = build_where({"has_phone": False})
    assert "phone IS NULL OR phone = ''" in where


def test_combined_filter_shape():
    where, params = build_where({"created_from": "2026-01-01", "has_email": True})
    assert where == "created_at >= $1 AND email IS NOT NULL AND email <> ''"
    assert len(params) == 1
