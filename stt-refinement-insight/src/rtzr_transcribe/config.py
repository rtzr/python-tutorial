from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from dotenv import dotenv_values

SUPPORTED_EXTENSIONS = frozenset({".mp4", ".m4a", ".mp3", ".amr", ".flac", ".wav"})
DEFAULT_INSIGHT_PROMPT = (
    "음성의 핵심 내용을 한국어로 간결하게 요약하고, "
    "중요한 요청·결정·후속 조치가 있으면 함께 정리해 주세요."
)


@dataclass(frozen=True)
class Settings:
    client_id: str
    client_secret: str
    base_url: str


def transcription_config(
    insight_prompt: str | None = DEFAULT_INSIGHT_PROMPT,
    *,
    use_refinement: bool = False,
    use_insight: bool = False,
    speaker_count: int | None = None,
) -> dict[str, Any]:
    if speaker_count is not None and (
        isinstance(speaker_count, bool) or not isinstance(speaker_count, int) or speaker_count < 1
    ):
        raise ValueError("speaker_count는 1 이상의 정수여야 합니다.")

    config: dict[str, Any] = {
        "model_name": "sommers",
        "language": "ko",
        "domain": "GENERAL",
        "use_diarization": True,
        "use_refinement": use_refinement,
        "use_insight": use_insight,
    }
    if speaker_count is not None:
        config["diarization"] = {"spk_count": speaker_count}
    prompt = insight_prompt.strip() if insight_prompt is not None else ""
    if use_insight and prompt:
        config["insight"] = {"prompt": prompt}
    return config


def _clean(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _setting(name: str, file_values: dict[str, object | None]) -> str:
    return _clean(os.environ.get(name)) or _clean(file_values.get(name))


def _validate_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    parsed = urlsplit(base_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(character.isspace() for character in base_url)
    ):
        raise ValueError("RTZR_BASE_URL은 https://로 시작하는 유효한 URL이어야 합니다.")
    return base_url


def load_settings(env_file: str | Path = ".env") -> Settings:
    path = Path(env_file)
    file_values = dict(dotenv_values(path)) if path.is_file() else {}
    client_id = _setting("RTZR_CLIENT_ID", file_values)
    client_secret = _setting("RTZR_CLIENT_SECRET", file_values)
    base_url = _setting("RTZR_BASE_URL", file_values)

    if not client_id:
        raise ValueError("RTZR_CLIENT_ID를 환경 변수 또는 .env에 설정하세요.")
    if not client_secret:
        raise ValueError("RTZR_CLIENT_SECRET을 환경 변수 또는 .env에 설정하세요.")
    if not base_url:
        raise ValueError("RTZR_BASE_URL을 환경 변수 또는 .env에 설정하세요.")

    return Settings(client_id, client_secret, _validate_base_url(base_url))
