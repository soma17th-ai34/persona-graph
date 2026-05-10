from __future__ import annotations

from datetime import datetime
import re


def terminal_log(event: str, **fields: object) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    detail = " ".join(
        f"{key}={format_log_value(value)}"
        for key, value in fields.items()
        if value is not None
    )
    print(f"[PersonaGraph {timestamp}] {event} {detail}".rstrip(), flush=True)


def format_log_value(value: object) -> str:
    text = preview(str(value), max_length=180)
    if not text:
        return '""'
    if re.search(r"\s", text):
        return f'"{text}"'
    return text


def preview(content: str, max_length: int = 120) -> str:
    collapsed = " ".join(content.split())
    if len(collapsed) <= max_length:
        return collapsed
    return f"{collapsed[: max_length - 1].rstrip()}..."
