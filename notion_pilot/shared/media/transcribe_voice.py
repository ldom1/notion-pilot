"""Local speech-to-text using Faster Whisper (open-source, on-device)"""

from pathlib import Path

from faster_whisper import WhisperModel
from loguru import logger


def transcribe_file(
    audio_path: str | Path, language: str = "fr", model_size: str = "base"
) -> str | None:
    """Transcribe an audio file (e.g. mp3, wav, ogg, flac, m4a) to plain text.

    Requires ``faster-whisper`` (declared in the main project dependencies). The chosen model
    is downloaded on first use (size depends on ``model_size``).

    Args:
        audio_path: Path to the audio file on disk.
        language: Whisper language code (default ``fr``).
        model_size: One of ``tiny``, ``base``, ``small``, ``medium``, ``large``.

    Returns:
        Stripped transcript, or ``None`` if the file is missing, the library is not
        installed, or transcription fails.
    """
    path = Path(audio_path)
    if not path.is_file():
        logger.error("Audio file not found: {}", audio_path)
        return None
    if WhisperModel is None:
        logger.error("faster-whisper not installed. Run: uv sync")
        return None

    try:
        logger.info("Transcribing: {} (model: {})", path.name, model_size)
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(path), language=language)
        text = "".join(segment.text for segment in segments)
        logger.info("Transcribed {:.1f}s audio", info.duration)
        return text.strip()
    except Exception as exc:  # noqa: BLE001  # pylint: disable=broad-exception-caught
        logger.error("Transcription failed: {}", exc)
        return None
