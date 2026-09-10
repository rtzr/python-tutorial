from __future__ import annotations

import json
import math
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

POLL_INTERVAL_SECONDS = 5.0
DEFAULT_TIMEOUT_SECONDS = 3600.0
REQUEST_TIMEOUT_SECONDS = 60.0
TRANSIENT_GET_STATUSES = {429, 500, 502, 503, 504}
RETRY_BACKOFF_SECONDS = (1.0, 2.0, 4.0)

ProgressCallback = Callable[[str, str], None]


class RTZRError(RuntimeError):
    """Base class for safe, user-facing RTZR errors."""


def _api_request_error(operation: str, status: int, code: str | None = None) -> RTZRError:
    suffix = f", API code {code}" if code else ""
    shown_status = str(status) if status else "network"
    return RTZRError(f"{operation} 실패 (HTTP {shown_status}{suffix})")


def _enterprise_error(features: tuple[str, ...]) -> RTZRError:
    requested = " 및 ".join(features)
    return RTZRError(
        f"{requested} 기능은 Enterprise 권한이 있는 계정에서만 사용할 수 있습니다.\n"
        "요금제 안내: https://developers.rtzr.ai/docs/pricing/#plans"
    )


def _timeout_error(timeout: float) -> RTZRError:
    return RTZRError(
        f"전체 처리 제한 {timeout:g}초를 초과했습니다.\n--timeout 값을 늘려 다시 실행하세요."
    )


def validate_timeout(timeout: float) -> None:
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout은 0보다 큰 유한한 수여야 합니다.")


def _json_object(response: requests.Response, operation: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RTZRError(f"{operation} 응답이 유효한 JSON이 아닙니다.") from exc
    if not isinstance(payload, dict):
        raise RTZRError(f"{operation} 응답의 최상위 형식이 객체가 아닙니다.")
    return payload


def _error_code(response: requests.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    for candidate in (
        payload.get("code"),
        payload.get("error", {}).get("code") if isinstance(payload.get("error"), dict) else None,
        payload.get("refine_error", {}).get("code")
        if isinstance(payload.get("refine_error"), dict)
        else None,
    ):
        if candidate is not None:
            return str(candidate)
    return None


def _payload_error_code(payload: dict[str, Any], field: str) -> str:
    error = payload.get(field)
    code = error.get("code") if isinstance(error, dict) else None
    return str(code) if code is not None else "UNKNOWN"


class RTZRClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str,
        *,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._sleep = sleep
        self._monotonic = monotonic
        self._access_token: str | None = None

    def authenticate(self) -> None:
        try:
            response = self._session.post(
                f"{self._base_url}/v1/authenticate",
                headers={
                    "accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"client_id": self._client_id, "client_secret": self._client_secret},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.RequestException as exc:
            raise RTZRError("인증 서버에 연결하지 못했습니다.") from exc
        if not 200 <= response.status_code < 300:
            raise _api_request_error("인증", response.status_code, _error_code(response))
        payload = _json_object(response, "인증")
        token = payload.get("access_token")
        if not isinstance(token, str) or not token:
            raise RTZRError("인증 응답에 유효한 access_token이 없습니다.")
        self._access_token = token

    def _request(
        self,
        method: str,
        url: str,
        *,
        operation: str,
        retry_get: bool,
        enterprise_features: tuple[str, ...] = (),
        **kwargs: Any,
    ) -> requests.Response:
        if self._access_token is None:
            self.authenticate()

        retries = 0
        reauthenticated = False
        base_headers = dict(kwargs.pop("headers", {}))
        while True:
            headers = dict(base_headers)
            headers["Authorization"] = f"Bearer {self._access_token}"
            try:
                response = self._session.request(
                    method,
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT_SECONDS,
                    **kwargs,
                )
            except requests.RequestException as exc:
                if retry_get and retries < len(RETRY_BACKOFF_SECONDS):
                    self._sleep(RETRY_BACKOFF_SECONDS[retries])
                    retries += 1
                    continue
                raise _api_request_error(operation, 0, "NETWORK_ERROR") from exc

            if response.status_code == 401 and not reauthenticated:
                self.authenticate()
                reauthenticated = True
                files = kwargs.get("files", {})
                for file_value in files.values():
                    file_object = file_value[1] if isinstance(file_value, tuple) else file_value
                    if hasattr(file_object, "seek"):
                        file_object.seek(0)
                continue

            if (
                retry_get
                and response.status_code in TRANSIENT_GET_STATUSES
                and retries < len(RETRY_BACKOFF_SECONDS)
            ):
                self._sleep(RETRY_BACKOFF_SECONDS[retries])
                retries += 1
                continue

            if not 200 <= response.status_code < 300:
                code = _error_code(response)
                if response.status_code == 403 and code == "H0003" and enterprise_features:
                    raise _enterprise_error(enterprise_features)
                raise _api_request_error(operation, response.status_code, code)
            return response

    def submit(self, audio_path: Path, config: dict[str, Any]) -> str:
        enterprise_features = []
        if config.get("use_refinement"):
            enterprise_features.append("전사 결과 보정")
        if config.get("use_insight"):
            enterprise_features.append("인사이트")

        upload_name = f"audio{audio_path.suffix.lower()}"
        try:
            with audio_path.open("rb") as audio:
                response = self._request(
                    "POST",
                    f"{self._base_url}/v1/transcribe",
                    operation="전사 생성",
                    retry_get=False,
                    enterprise_features=tuple(enterprise_features),
                    headers={"accept": "application/json"},
                    data={
                        "config": json.dumps(
                            config,
                            ensure_ascii=False,
                            allow_nan=False,
                            separators=(",", ":"),
                        )
                    },
                    files={"file": (upload_name, audio)},
                )
        except OSError as exc:
            raise RTZRError(f"오디오 파일을 읽을 수 없습니다: {audio_path}") from exc
        payload = _json_object(response, "전사 생성")
        transcribe_id = payload.get("id")
        if not isinstance(transcribe_id, str) or not transcribe_id:
            raise RTZRError("전사 생성 응답에 유효한 id가 없습니다.")
        return transcribe_id

    def get(self, transcribe_id: str, *, refined: bool = False) -> dict[str, Any]:
        encoded_id = quote(transcribe_id, safe="")
        params = {"result": "refined"} if refined else None
        response = self._request(
            "GET",
            f"{self._base_url}/v1/transcribe/{encoded_id}",
            operation="보정 결과 조회" if refined else "기본 전사 조회",
            retry_get=True,
            headers={"accept": "application/json"},
            params=params,
        )
        return _json_object(response, "보정 결과 조회" if refined else "기본 전사 조회")

    def _wait(self, deadline: float, timeout: float) -> None:
        remaining = deadline - self._monotonic()
        if remaining <= 0:
            raise _timeout_error(timeout)
        self._sleep(min(POLL_INTERVAL_SECONDS, remaining))

    def wait_for_base(
        self,
        transcribe_id: str,
        *,
        deadline: float,
        timeout: float,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        previous: str | None = None
        while True:
            if self._monotonic() >= deadline:
                raise _timeout_error(timeout)
            payload = self.get(transcribe_id)
            status = payload.get("status")
            if status != previous and progress is not None:
                progress("base", str(status))
            previous = str(status)

            if status == "completed":
                results = payload.get("results")
                utterances = results.get("utterances") if isinstance(results, dict) else None
                if not isinstance(utterances, list):
                    raise RTZRError("완료 응답에 results.utterances 배열이 없습니다.")
                return payload
            if status == "failed":
                raise RTZRError(
                    f"기본 전사 처리 실패 (API code {_payload_error_code(payload, 'error')})"
                )
            if status != "transcribing":
                raise RTZRError(f"알 수 없는 기본 전사 상태입니다: {status!r}")
            self._wait(deadline, timeout)

    def wait_for_refinement(
        self,
        transcribe_id: str,
        *,
        deadline: float,
        timeout: float,
        progress: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        previous: str | None = None
        while True:
            if self._monotonic() >= deadline:
                raise _timeout_error(timeout)
            payload = self.get(transcribe_id, refined=True)
            base_status = payload.get("status")
            if base_status == "failed":
                raise RTZRError(
                    f"기본 전사 처리 실패 (API code {_payload_error_code(payload, 'error')})"
                )

            refinement_status = (
                "transcribing" if base_status == "transcribing" else payload.get("refine_status")
            )
            shown_status = str(refinement_status)
            if shown_status != previous and progress is not None:
                progress("refinement", shown_status)
            previous = shown_status

            if base_status == "transcribing":
                self._wait(deadline, timeout)
                continue
            if base_status != "completed":
                raise RTZRError(f"알 수 없는 기본 전사 상태입니다: {base_status!r}")
            if refinement_status == "completed":
                results = payload.get("results")
                utterances = results.get("utterances") if isinstance(results, dict) else None
                if not isinstance(utterances, list):
                    raise RTZRError("보정 완료 응답에 results.utterances 배열이 없습니다.")
                return payload
            if refinement_status == "failed":
                raise RTZRError(
                    f"전사 결과 보정 실패 (API code {_payload_error_code(payload, 'refine_error')})"
                )
            if refinement_status not in {"queued", "processing"}:
                raise RTZRError(
                    "보정 결과를 확인할 수 없습니다.\n문제가 반복되면 RTZR 지원팀에 문의하세요."
                )
            self._wait(deadline, timeout)
