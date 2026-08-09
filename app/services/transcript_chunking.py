import re


TRANSCRIPT_CHUNK_SIZE_CHARS = 1200
TRANSCRIPT_CHUNK_OVERLAP_CHARS = 200

_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WHITESPACE = re.compile(r"\s+")


def chunk_transcript(
    transcript: str,
    *,
    chunk_size: int = TRANSCRIPT_CHUNK_SIZE_CHARS,
    overlap: int = TRANSCRIPT_CHUNK_OVERLAP_CHARS,
) -> list[str]:
    """Split a transcript at natural boundaries with deterministic overlap."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be non-negative and smaller than chunk_size")

    text = _normalize_transcript(transcript)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0

    while start < len(text):
        end = _find_chunk_end(text, start, chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break

        next_start = _find_next_start(text, start, end, overlap)
        start = next_start if next_start > start else _skip_whitespace(text, end)

    return chunks


def _normalize_transcript(transcript: str) -> str:
    normalized = transcript.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs: list[str] = []
    current_lines: list[str] = []

    for line in normalized.split("\n"):
        stripped = " ".join(line.split())
        if stripped:
            current_lines.append(stripped)
        elif current_lines:
            paragraphs.append(" ".join(current_lines))
            current_lines = []

    if current_lines:
        paragraphs.append(" ".join(current_lines))

    return "\n\n".join(paragraphs)


def _find_chunk_end(text: str, start: int, chunk_size: int) -> int:
    limit = min(start + chunk_size, len(text))
    if limit == len(text):
        return limit

    minimum_boundary = start + chunk_size // 2

    paragraph_boundary = text.rfind("\n\n", minimum_boundary, limit)
    if paragraph_boundary != -1:
        return paragraph_boundary

    sentence_boundary = _last_sentence_boundary(text, minimum_boundary, limit)
    if sentence_boundary is not None:
        return sentence_boundary

    whitespace_boundary = _last_whitespace_boundary(text, minimum_boundary, limit)
    if whitespace_boundary is not None:
        return whitespace_boundary

    next_whitespace = _WHITESPACE.search(text, limit)
    return next_whitespace.start() if next_whitespace is not None else len(text)


def _last_sentence_boundary(text: str, start: int, end: int) -> int | None:
    boundary: int | None = None
    for match in _SENTENCE_BOUNDARY.finditer(text, start, end):
        boundary = match.start()
    return boundary


def _last_whitespace_boundary(text: str, start: int, end: int) -> int | None:
    boundary: int | None = None
    for match in _WHITESPACE.finditer(text, start, end):
        boundary = match.start()
    return boundary


def _find_next_start(text: str, start: int, end: int, overlap: int) -> int:
    if overlap == 0:
        return _skip_whitespace(text, end)

    desired_start = max(start, end - overlap)
    if desired_start == start:
        return _skip_whitespace(text, end)
    if desired_start >= len(text):
        return len(text)

    if text[desired_start - 1].isspace():
        return _skip_whitespace(text, desired_start)

    next_boundary = _WHITESPACE.search(text, desired_start, end)
    if next_boundary is None:
        return _skip_whitespace(text, end)
    return _skip_whitespace(text, next_boundary.end())


def _skip_whitespace(text: str, position: int) -> int:
    while position < len(text) and text[position].isspace():
        position += 1
    return position
