from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from rtzr_transcribe.client import (
    DEFAULT_TIMEOUT_SECONDS,
    RTZRClient,
    RTZRError,
    validate_timeout,
)
from rtzr_transcribe.config import (
    DEFAULT_INSIGHT_PROMPT,
    load_settings,
    transcription_config,
)
from rtzr_transcribe.formatters import insight_text, transcript_text
from rtzr_transcribe.io import (
    default_output_directory,
    validate_audio_path,
    validate_output_directory,
    write_json,
    write_text,
)

STATUS_MESSAGES = {
    ("base", "transcribing"): "기본 전사를 처리하고 있습니다.",
    ("base", "completed"): "기본 전사가 완료되었습니다.",
    ("refinement", "transcribing"): "기본 전사 완료를 기다리고 있습니다.",
    ("refinement", "queued"): "전사 결과 보정을 기다리고 있습니다.",
    ("refinement", "processing"): "전사 결과를 보정하고 있습니다.",
    ("refinement", "completed"): "전사 결과 보정이 완료되었습니다.",
}


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요.") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("1 이상의 정수를 입력하세요.")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rtzr-transcribe",
        description="한국어 음성을 전사하고 선택적으로 보정 결과와 인사이트를 저장합니다.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("audio", type=Path, help="전사할 음성 파일")
    parser.add_argument("--output-dir", type=Path, help="결과를 저장할 빈 디렉터리")
    parser.add_argument(
        "--insight-prompt",
        default=None,
        help="인사이트 생성 관점 또는 지시문",
    )
    parser.add_argument(
        "--insight",
        action="store_true",
        help="인사이트 생성을 요청함",
    )
    parser.add_argument(
        "--refinement",
        action="store_true",
        help="전사 결과 보정을 요청함",
    )
    parser.add_argument(
        "--speaker-count",
        type=_positive_int,
        help="예상 화자 수(생략 시 자동 예측)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="전체 결과 대기 제한(초)",
    )
    return parser


def _show_progress(stage: str, status: str) -> None:
    print(STATUS_MESSAGES.get((stage, status), f"{stage} 상태: {status}"), file=sys.stderr)


def _show_error(error: Exception, *, transcribe_id: str | None, stage: str) -> None:
    print(f"오류: {error}", file=sys.stderr)
    print(f"작업 ID: {transcribe_id or '생성되지 않음'}", file=sys.stderr)
    print(f"처리 단계: {stage}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.insight_prompt is not None and not args.insight:
        parser.error("--insight-prompt는 --insight와 함께 사용해야 합니다.")

    transcribe_id: str | None = None
    stage = "입력 및 설정 확인"
    try:
        validate_audio_path(args.audio)
        output_dir = args.output_dir or default_output_directory(args.audio)
        validate_output_directory(output_dir)
        config = transcription_config(
            DEFAULT_INSIGHT_PROMPT if args.insight_prompt is None else args.insight_prompt,
            use_refinement=args.refinement,
            use_insight=args.insight,
            speaker_count=args.speaker_count,
        )
        settings = load_settings()

        print("인증 후 전사 작업을 생성합니다.", file=sys.stderr)
        client = RTZRClient(settings.client_id, settings.client_secret, settings.base_url)
        validate_timeout(args.timeout)
        stage = "전사 작업 생성"
        transcribe_id = client.submit(args.audio, config)
        print(f"작업 ID: {transcribe_id}", file=sys.stderr)
        deadline = time.monotonic() + args.timeout
        stage = "기본 전사 조회"
        base = client.wait_for_base(
            transcribe_id,
            deadline=deadline,
            timeout=args.timeout,
            progress=_show_progress,
        )
        stage = "기본 전사 응답 저장"
        write_json(output_dir / "response.json", base)

        refined = None
        if args.refinement:
            stage = "보정 결과 조회"
            refined = client.wait_for_refinement(
                transcribe_id,
                deadline=deadline,
                timeout=args.timeout,
                progress=_show_progress,
            )
            stage = "보정 응답 저장"
            write_json(output_dir / "refined.json", refined)
        stage = "전사 TXT 변환 및 저장"
        final_response = refined if refined is not None else base
        transcript = transcript_text(final_response)
        write_text(output_dir / "transcript.txt", transcript)

        insight: str | None = None
        if args.insight:
            stage = "인사이트 TXT 변환 및 저장"
            insight = insight_text(base)
            write_text(output_dir / "insight.txt", insight)

        print("\n보정 전사" if refined is not None else "\n기본 전사")
        print(transcript.rstrip() or "(발화 없음)")
        if insight is not None:
            print("\n인사이트")
            print(insight.rstrip())
        print(f"\n결과 저장: {output_dir}")
        return 0
    except (OSError, RTZRError, TypeError, ValueError) as exc:
        _show_error(exc, transcribe_id=transcribe_id, stage=stage)
        return 2
    except KeyboardInterrupt:
        print("\n오류: 사용자 요청으로 중단했습니다.", file=sys.stderr)
        return 130
