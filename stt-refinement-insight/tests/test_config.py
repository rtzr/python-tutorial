from __future__ import annotations

import pytest

from rtzr_transcribe.config import load_settings


def test_load_settings_resolves_sources_and_requires_https(tmp_path, monkeypatch) -> None:
    for name in ("RTZR_CLIENT_ID", "RTZR_CLIENT_SECRET", "RTZR_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "RTZR_CLIENT_ID=file-id\n"
        "RTZR_CLIENT_SECRET=file-secret\n"
        "RTZR_BASE_URL=https://example.test/\n",
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.client_id == "file-id"
    assert settings.client_secret == "file-secret"
    assert settings.base_url == "https://example.test"
    monkeypatch.setenv("RTZR_CLIENT_ID", "env-id")
    monkeypatch.setenv("RTZR_CLIENT_SECRET", "env-secret")
    monkeypatch.setenv("RTZR_BASE_URL", "https://env.example")

    settings = load_settings(env_file)

    assert settings.client_id == "env-id"
    assert settings.client_secret == "env-secret"
    assert settings.base_url == "https://env.example"

    monkeypatch.setenv("RTZR_BASE_URL", "http://example.test")

    with pytest.raises(ValueError, match="https://"):
        load_settings(env_file)
