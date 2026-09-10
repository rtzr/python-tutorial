from __future__ import annotations

from pathlib import Path

import pytest

from rtzr_transcribe.io import validate_audio_path


def test_unsupported_or_empty_audio_is_rejected(tmp_path: Path) -> None:
    unsupported = tmp_path / "sample.ogg"
    unsupported.write_bytes(b"audio")
    empty = tmp_path / "sample.wav"
    empty.touch()

    with pytest.raises(ValueError, match="지원하지 않는"):
        validate_audio_path(unsupported)
    with pytest.raises(ValueError, match="비어 있습니다"):
        validate_audio_path(empty)
