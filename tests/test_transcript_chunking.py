import pytest

from app.services.transcript_chunking import chunk_transcript


@pytest.mark.parametrize("transcript", ["", "   ", "\n\n\t"])
def test_empty_transcript_creates_no_chunks(transcript: str) -> None:
    assert chunk_transcript(transcript) == []


def test_short_transcript_creates_one_normalized_chunk() -> None:
    transcript = "  We approved the launch plan.  \nThe release is on Monday.  "

    assert chunk_transcript(transcript) == [
        "We approved the launch plan. The release is on Monday."
    ]


def test_long_transcript_creates_deterministic_ordered_chunks() -> None:
    transcript = " ".join(f"topic-{index}" for index in range(80))

    first_result = chunk_transcript(transcript, chunk_size=100, overlap=20)
    second_result = chunk_transcript(transcript, chunk_size=100, overlap=20)

    assert first_result == second_result
    assert len(first_result) > 1
    assert first_result[0].startswith("topic-0 ")
    assert first_result[-1].endswith("topic-79")
    assert all(len(chunk) <= 100 for chunk in first_result)
    assert all(
        word in transcript.split()
        for chunk in first_result
        for word in chunk.split()
    )


def test_chunks_overlap_on_complete_words() -> None:
    transcript = " ".join(f"word{index}" for index in range(40))
    chunks = chunk_transcript(transcript, chunk_size=80, overlap=20)

    for previous, current in zip(chunks, chunks[1:]):
        previous_words = previous.split()
        current_words = current.split()
        overlap_lengths = range(1, min(len(previous_words), len(current_words)) + 1)

        assert any(
            previous_words[-length:] == current_words[:length]
            for length in overlap_lengths
        )


def test_chunking_prefers_paragraph_boundaries() -> None:
    transcript = (
        "First paragraph has a complete thought.\n\n"
        "Second paragraph also has useful context.\n\n"
        "Third paragraph closes the discussion."
    )

    chunks = chunk_transcript(transcript, chunk_size=70, overlap=15)

    assert chunks == [
        "First paragraph has a complete thought.",
        "thought.\n\nSecond paragraph also has useful context.",
        "useful context.\n\nThird paragraph closes the discussion.",
    ]


@pytest.mark.parametrize(
    ("chunk_size", "overlap"),
    [(0, 0), (100, -1), (100, 100)],
)
def test_chunking_rejects_invalid_parameters(chunk_size: int, overlap: int) -> None:
    with pytest.raises(ValueError):
        chunk_transcript("Transcript", chunk_size=chunk_size, overlap=overlap)
