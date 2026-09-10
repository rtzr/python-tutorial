from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rtzr_transcribe import cli
from rtzr_transcribe.config import Settings

BASE_RESULT = {
    "status": "completed",
    "results": {
        "utterances": [{"spk": 0, "msg": "기본 전사"}],
        "insight": [
            {
                "title": "회의 요약",
                "category": "업무",
                "summary": "결정 사항을 정리했습니다.",
            }
        ],
    },
}
REFINED_RESULT = {
    "status": "completed",
    "refine_status": "completed",
    "results": {"utterances": [{"spk": 1, "msg": "보정된 전사입니다."}]},
}


class FakeClient:
    received_config: dict[str, Any] | None = None
    deadline: float | None = None

    def __init__(self, client_id: str, client_secret: str, base_url: str) -> None:
        assert (client_id, client_secret, base_url) == (
            "client",
            "secret",
            "https://api.example.test",
        )

    def submit(self, audio_path: Path, config: dict[str, Any]) -> str:
        assert audio_path.is_file()
        self.__class__.received_config = config
        return "job-1"

    def wait_for_base(
        self,
        transcribe_id: str,
        *,
        deadline: float,
        timeout: float,
        progress: Any,
    ) -> dict[str, Any]:
        assert transcribe_id == "job-1"
        assert timeout == 3600
        self.__class__.deadline = deadline
        progress("base", "completed")
        return BASE_RESULT

    def wait_for_refinement(
        self,
        transcribe_id: str,
        *,
        deadline: float,
        timeout: float,
        progress: Any,
    ) -> dict[str, Any]:
        assert transcribe_id == "job-1"
        assert timeout == 3600
        assert deadline == self.__class__.deadline
        progress("refinement", "completed")
        return REFINED_RESULT


def test_cli_can_enable_both_features_and_print_readable_result(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    audio = tmp_path / "한국어 음성.flac"
    audio.write_bytes(b"audio")
    output = tmp_path / "result"
    monkeypatch.setattr(cli, "RTZRClient", FakeClient)
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings("client", "secret", "https://api.example.test"),
    )

    exit_code = cli.main(
        [
            str(audio),
            "--output-dir",
            str(output),
            "--refinement",
            "--insight",
            "--insight-prompt",
            "결정 사항만 알려 주세요.",
            "--speaker-count",
            "2",
        ]
    )

    assert exit_code == 0
    assert FakeClient.received_config is not None
    assert FakeClient.received_config["insight"] == {"prompt": "결정 사항만 알려 주세요."}
    assert FakeClient.received_config["diarization"] == {"spk_count": 2}
    assert (output / "transcript.txt").read_text(encoding="utf-8") == (
        "화자 2: 보정된 전사입니다.\n"
    )
    assert "제목: 회의 요약" in (output / "insight.txt").read_text(encoding="utf-8")
    assert json.loads((output / "response.json").read_text(encoding="utf-8")) == BASE_RESULT
    assert json.loads((output / "refined.json").read_text(encoding="utf-8")) == REFINED_RESULT
    captured = capsys.readouterr()
    assert "보정된 전사입니다." in captured.out
    assert "결정 사항을 정리했습니다." in captured.out


def test_cli_defaults_to_base_transcription(tmp_path: Path, monkeypatch, capsys) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"audio")
    output = tmp_path / "result"
    monkeypatch.setattr(cli, "RTZRClient", FakeClient)
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings("client", "secret", "https://api.example.test"),
    )

    exit_code = cli.main([str(audio), "--output-dir", str(output)])

    assert exit_code == 0
    assert FakeClient.received_config is not None
    assert FakeClient.received_config["use_insight"] is False
    assert FakeClient.received_config["use_refinement"] is False
    assert "insight" not in FakeClient.received_config
    assert not (output / "insight.txt").exists()
    assert not (output / "refined.json").exists()
    assert (output / "transcript.txt").read_text(encoding="utf-8") == "화자 1: 기본 전사\n"
    assert "\n인사이트\n" not in capsys.readouterr().out


def test_cli_preserves_completed_outputs_when_insight_conversion_fails(
    tmp_path: Path, monkeypatch
) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"audio")
    output = tmp_path / "result"
    FakeClient.received_config = None
    FakeClient.deadline = None
    monkeypatch.setattr(cli, "RTZRClient", FakeClient)
    monkeypatch.setattr(
        cli,
        "load_settings",
        lambda: Settings("client", "secret", "https://api.example.test"),
    )

    def fail_conversion(_response: dict[str, Any]) -> str:
        raise ValueError("인사이트 TXT 변환 실패")

    monkeypatch.setattr(cli, "insight_text", fail_conversion)

    exit_code = cli.main([str(audio), "--output-dir", str(output), "--refinement", "--insight"])

    assert exit_code == 2
    assert json.loads((output / "response.json").read_text(encoding="utf-8")) == BASE_RESULT
    assert json.loads((output / "refined.json").read_text(encoding="utf-8")) == REFINED_RESULT
    assert (output / "transcript.txt").read_text(encoding="utf-8") == (
        "화자 2: 보정된 전사입니다.\n"
    )
    assert not (output / "insight.txt").exists()
