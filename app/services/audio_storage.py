from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile

ALLOWED_AUDIO_EXTENSIONS = {".m4a", ".mp3", ".wav"}
MAX_UPLOAD_SIZE_BYTES = 50 * 1024 * 1024
UPLOAD_CHUNK_SIZE_BYTES = 1024 * 1024


class UnsupportedAudioExtensionError(ValueError):
    pass


class EmptyAudioFileError(ValueError):
    pass


class AudioFileTooLargeError(ValueError):
    pass


@dataclass(frozen=True)
class StoredAudio:
    filename: str
    size_bytes: int


class AudioStorage:
    def __init__(self, root: Path = Path("storage/audio")) -> None:
        self.root = root

    async def save(self, meeting_id: UUID, upload: UploadFile) -> StoredAudio:
        extension = Path(upload.filename or "").suffix.lower()
        if extension not in ALLOWED_AUDIO_EXTENSIONS:
            raise UnsupportedAudioExtensionError(
                "Only .mp3, .wav, and .m4a audio files are supported"
            )

        meeting_directory = self.root / str(meeting_id)
        meeting_directory.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid4()}{extension}"
        destination = meeting_directory / filename
        size_bytes = 0

        try:
            with destination.open("xb") as output:
                while chunk := await upload.read(UPLOAD_CHUNK_SIZE_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
                        raise AudioFileTooLargeError("Audio file exceeds the 50 MB limit")
                    output.write(chunk)

            if size_bytes == 0:
                raise EmptyAudioFileError("Audio file must not be empty")
        except BaseException:
            destination.unlink(missing_ok=True)
            raise

        return StoredAudio(filename=filename, size_bytes=size_bytes)

    def resolve(self, meeting_id: UUID, filename: str) -> Path:
        meeting_directory = (self.root / str(meeting_id)).resolve()
        audio_path = (meeting_directory / filename).resolve()

        if audio_path.parent != meeting_directory:
            raise ValueError("Audio filename escapes the meeting directory")

        return audio_path


def get_audio_storage() -> AudioStorage:
    return AudioStorage()
