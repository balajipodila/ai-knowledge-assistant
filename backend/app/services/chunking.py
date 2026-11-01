import re


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_SENTENCE_END = re.compile(r"[.!?](?:\s+|$)")


def _overlap_suffix(text: str, overlap: int) -> str:
    if overlap == 0:
        return ""
    suffix = text[-overlap:]
    first_space = suffix.find(" ")
    if first_space >= 0:
        suffix = suffix[first_space + 1 :]
    return suffix.strip()


def _split_position(text: str, max_size: int) -> int:
    candidate = text[: max_size + 1]
    sentence_ends = [match.end() for match in _SENTENCE_END.finditer(candidate)]
    if sentence_ends:
        return sentence_ends[-1]
    boundary = max(candidate.rfind(" "), candidate.rfind("\n"))
    return boundary if boundary >= max_size // 2 else max_size


def _split_long_text(text: str, max_size: int, overlap: int) -> list[str]:
    remaining = text.strip()
    pieces: list[str] = []
    while len(remaining) > max_size:
        split_at = _split_position(remaining, max_size)
        piece = remaining[:split_at].strip()
        pieces.append(piece)
        remainder = remaining[split_at:].strip()
        if not remainder:
            break
        prefix = _overlap_suffix(piece, overlap)
        remaining = f"{prefix} {remainder}".strip() if prefix else remainder
    if remaining:
        pieces.append(remaining)
    return pieces


def _paragraph_pieces(text: str, max_size: int, overlap: int) -> list[str]:
    pieces: list[str] = []
    for paragraph in re.split(r"\n\s*\n", text):
        sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(paragraph)]
        current = ""
        for sentence in filter(None, sentences):
            if len(sentence) > max_size:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(_split_long_text(sentence, max_size, overlap))
                continue
            candidate = f"{current} {sentence}".strip()
            if len(candidate) > max_size and current:
                pieces.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            pieces.append(current)
    return pieces


def chunk_text(text: str, *, chunk_size: int, overlap: int) -> list[str]:
    if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Chunk size must be positive and overlap smaller than size.")

    paragraphs = _paragraph_pieces(text, chunk_size, overlap)
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            chunks.append(current)
            prefix = _overlap_suffix(current, overlap)
            available_prefix_size = max(0, chunk_size - len(paragraph) - 2)
            if len(prefix) > available_prefix_size:
                prefix = prefix[-available_prefix_size:] if available_prefix_size else ""
            current = f"{prefix}\n\n{paragraph}".strip()
        else:
            chunks.extend(_split_long_text(paragraph, chunk_size, overlap))

    if current:
        chunks.append(current)
    return chunks
