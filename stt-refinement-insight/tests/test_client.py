from __future__ import annotations

import time
from pathlib import Path

import pytest
import requests
import responses

from rtzr_transcribe.client import (
    RTZRClient,
    RTZRError,
)
from rtzr_transcribe.config import transcription_config

BASE_URL = "https://api.example.test"
BASE_RESULT = {
    "id": "job-1",
    "status": "completed",
    "results": {
        "utterances": [{"msg": "기본 전사"}],
        "insight": [{"title": "제목", "category": "업무", "summary": "요약"}],
    },
}
REFINED_RESULT = {
    "id": "job-1",
    "status": "completed",
    "refine_status": "completed",
    "results": {"utterances": [{"msg": "보정 전사"}]},
}


def add_auth(token: str = "token") -> None:
    responses.add(
        responses.POST,
        f"{BASE_URL}/v1/authenticate",
        json={"access_token": token},
        status=200,
    )


@responses.activate
def test_full_pipeline_submits_once_and_polls_both_results(tmp_path: Path) -> None:
    audio = tmp_path / "voice.wav"
    audio.write_bytes(b"wave-data")
    add_auth()
    responses.add(
        responses.POST,
        f"{BASE_URL}/v1/transcribe",
        json={"id": "job-1"},
        status=200,
    )
    responses.add(
        responses.GET,
        f"{BASE_URL}/v1/transcribe/job-1",
        json={"id": "job-1", "status": "transcribing"},
    )
    responses.add(responses.GET, f"{BASE_URL}/v1/transcribe/job-1", json=BASE_RESULT)
    responses.add(
        responses.GET,
        f"{BASE_URL}/v1/transcribe/job-1",
        json={"id": "job-1", "status": "completed", "refine_status": "queued"},
    )
    responses.add(responses.GET, f"{BASE_URL}/v1/transcribe/job-1", json=REFINED_RESULT)
    client = RTZRClient("client", "secret", BASE_URL, sleep=lambda _: None)

    transcribe_id = client.submit(
        audio, transcription_config(use_refinement=True, use_insight=True, speaker_count=2)
    )
    deadline = time.monotonic() + 10
    base = client.wait_for_base(
        transcribe_id,
        deadline=deadline,
        timeout=10,
    )
    refined = client.wait_for_refinement(
        transcribe_id,
        deadline=deadline,
        timeout=10,
    )

    assert base == BASE_RESULT
    assert refined == REFINED_RESULT
    submit_calls = [call for call in responses.calls if call.request.method == "POST"]
    assert len(submit_calls) == 2
    request_body = submit_calls[1].request.body
    assert isinstance(request_body, bytes)
    assert b'filename="audio.wav"' in request_body
    assert b'"language":"ko"' in request_body
    assert b'"use_diarization":true' in request_body
    assert b'"diarization":{"spk_count":2}' in request_body
    assert b'"use_refinement":true' in request_body
    assert b'"use_insight":true' in request_body
    assert responses.calls[-1].request.url.endswith("?result=refined")


@responses.activate
def test_get_retries_a_transient_failure() -> None:
    add_auth()
    responses.add(responses.GET, f"{BASE_URL}/v1/transcribe/job-1", status=500, json={})
    responses.add(responses.GET, f"{BASE_URL}/v1/transcribe/job-1", json=BASE_RESULT)
    sleeps: list[float] = []
    client = RTZRClient("client", "secret", BASE_URL, sleep=sleeps.append)

    result = client.wait_for_base("job-1", deadline=time.monotonic() + 10, timeout=10)

    assert result == BASE_RESULT
    assert sleeps == [1.0]


@responses.activate
def test_get_reauthenticates_once_after_401() -> None:
    add_auth("old-token")
    responses.add(
        responses.GET,
        f"{BASE_URL}/v1/transcribe/job-1",
        status=401,
        json={"code": "H0002"},
    )
    add_auth("new-token")
    responses.add(responses.GET, f"{BASE_URL}/v1/transcribe/job-1", json=BASE_RESULT)
    client = RTZRClient("client", "secret", BASE_URL, sleep=lambda _: None)

    result = client.wait_for_base("job-1", deadline=time.monotonic() + 10, timeout=10)

    assert result == BASE_RESULT
    assert responses.calls[-1].request.headers["Authorization"] == "Bearer new-token"


@responses.activate
def test_submit_network_failure_is_not_retried(tmp_path: Path) -> None:
    audio = tmp_path / "voice.mp3"
    audio.write_bytes(b"audio")
    add_auth()
    responses.add(
        responses.POST,
        f"{BASE_URL}/v1/transcribe",
        body=requests.ConnectionError("offline"),
    )
    client = RTZRClient("client", "secret", BASE_URL, sleep=lambda _: None)

    with pytest.raises(RTZRError, match="NETWORK_ERROR"):
        client.submit(audio, transcription_config())

    assert len(responses.calls) == 2


@responses.activate
def test_refinement_failure_exposes_only_safe_code() -> None:
    add_auth()
    responses.add(
        responses.GET,
        f"{BASE_URL}/v1/transcribe/job-1",
        json={
            "status": "completed",
            "refine_status": "failed",
            "refine_error": {"code": "refiner_failed", "message": "private detail"},
        },
    )
    client = RTZRClient("client", "secret", BASE_URL, sleep=lambda _: None)

    with pytest.raises(RTZRError) as error:
        client.wait_for_refinement("job-1", deadline=time.monotonic() + 10, timeout=10)

    assert "refiner_failed" in str(error.value)
    assert "private detail" not in str(error.value)


def test_shared_deadline_times_out() -> None:
    clock = [0.0]

    def sleep(seconds: float) -> None:
        clock[0] += seconds

    client = RTZRClient(
        "client",
        "secret",
        BASE_URL,
        sleep=sleep,
        monotonic=lambda: clock[0],
    )
    client.get = lambda _transcribe_id, refined=False: {"status": "transcribing"}  # type: ignore[method-assign]

    with pytest.raises(RTZRError, match="5초"):
        client.wait_for_base("job-1", deadline=5.0, timeout=5.0)
