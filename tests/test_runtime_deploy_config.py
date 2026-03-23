from __future__ import annotations

from pathlib import Path

import pytest

import db
import main
import runtime_config


def test_initialize_app_creates_all_runtime_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    app_data_dir = tmp_path / "render-data"
    monkeypatch.setattr(main, "APP_DATA_DIR", app_data_dir)
    monkeypatch.setattr(main, "SOLUTIONS_DIR", app_data_dir / "solutions")
    monkeypatch.setattr(main, "SUBMISSIONS_DIR", app_data_dir / "submissions")
    monkeypatch.setattr(main, "TEACHER_CACHE_DIR", app_data_dir / "teacher")
    monkeypatch.setattr(main, "STUDENT_TMP_DIR", app_data_dir / "tmp" / "submissions")

    main.initialize_app()

    assert app_data_dir.exists()
    assert (app_data_dir / "solutions").exists()
    assert (app_data_dir / "submissions").exists()
    assert (app_data_dir / "teacher").exists()
    assert (app_data_dir / "tmp" / "submissions").exists()


def test_get_app_data_dir_uses_explicit_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    expected = tmp_path / "render-mounted-disk"
    monkeypatch.setenv("APP_DATA_DIR", str(expected))

    assert runtime_config.get_app_data_dir() == expected.resolve()


def test_get_cors_allow_origins_uses_explicit_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "CORS_ALLOW_ORIGINS",
        "https://frontend.example.com, https://admin.example.com/ , https://frontend.example.com",
    )
    monkeypatch.delenv("FRONTEND_BASE_URL", raising=False)

    assert runtime_config.get_cors_allow_origins() == [
        "https://frontend.example.com",
        "https://admin.example.com",
    ]


def test_get_cors_allow_origins_rejects_wildcard(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="CORS_ALLOW_ORIGINS"):
        runtime_config.get_cors_allow_origins()


def test_health_route_allows_frontend_origin_via_cors(client):
    response = client.get(
        "/health",
        headers={"Origin": "http://testserver"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["access-control-allow-origin"] == "http://testserver"


def test_create_database_engine_uses_pre_ping_and_respects_echo(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SQLALCHEMY_ECHO", "true")

    engine = db.create_database_engine("sqlite+pysqlite:///:memory:")
    try:
        assert engine.echo is True
        assert getattr(engine.pool, "_pre_ping", False) is True
    finally:
        engine.dispose()
