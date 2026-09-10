from __future__ import annotations

from typing import Any


def _speaker_label(utterance: dict[str, Any]) -> str | None:
    speaker = utterance.get("spk")
    if isinstance(speaker, int) and not isinstance(speaker, bool) and speaker >= 0:
        return f"화자 {speaker + 1}"
    return None


def transcript_text(response: dict[str, Any]) -> str:
    results = response.get("results")
    utterances = results.get("utterances") if isinstance(results, dict) else None
    if not isinstance(utterances, list):
        raise TypeError("응답에 results.utterances 배열이 없습니다.")

    messages: list[str] = []
    for index, utterance in enumerate(utterances):
        if not isinstance(utterance, dict):
            raise TypeError(f"results.utterances[{index}]가 객체가 아닙니다.")
        message = utterance.get("msg")
        if not isinstance(message, str):
            raise TypeError(f"results.utterances[{index}].msg가 문자열이 아닙니다.")
        if stripped := message.strip():
            speaker_label = _speaker_label(utterance)
            messages.append(f"{speaker_label}: {stripped}" if speaker_label else stripped)
    return "\n".join(messages) + ("\n" if messages else "")


def insight_text(response: dict[str, Any]) -> str:
    results = response.get("results")
    insights = results.get("insight") if isinstance(results, dict) else None
    if not isinstance(insights, list) or not insights:
        raise ValueError(
            "인사이트 결과를 확인할 수 없습니다.\n문제가 반복되면 RTZR 지원팀에 문의하세요."
        )

    blocks: list[str] = []
    for index, insight in enumerate(insights):
        if not isinstance(insight, dict):
            raise TypeError(f"results.insight[{index}]가 객체가 아닙니다.")
        values: dict[str, str] = {}
        for field in ("title", "category", "summary"):
            value = insight.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"results.insight[{index}].{field}가 유효한 문자열이 아닙니다.")
            values[field] = value.strip()
        blocks.append(
            f"제목: {values['title']}\n분류: {values['category']}\n내용: {values['summary']}"
        )
    return "\n\n".join(blocks) + "\n"
