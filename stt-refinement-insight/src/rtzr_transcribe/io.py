from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rtzr_transcribe.config import SUPPORTED_EXTENSIONS


def validate_audio_path(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"오디오 파일을 찾을 수 없습니다: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"오디오 파일이 비어 있습니다: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(
            f"지원하지 않는 파일 형식입니다: {path.suffix or '(확장자 없음)'} ({supported})"
        )


def default_output_directory(audio_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("outputs") / f"{audio_path.stem}-{timestamp}"


def validate_output_directory(path: Path) -> None:
    if path.exists() and not path.is_dir():
        raise ValueError(f"출력 경로가 디렉터리가 아닙니다: {path}")
    if path.is_dir() and any(path.iterdir()):
        raise ValueError(f"출력 디렉터리가 비어 있지 않습니다: {path}")


def _write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary_name = temporary.name
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            with suppress(FileNotFoundError):
                Path(temporary_name).unlink()


def write_text(path: Path, content: str) -> None:
    _write_atomic(path, content)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    content = json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    _write_atomic(path, content)
