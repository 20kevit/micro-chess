"""Audio boundary. No TTS provider yet; depend on this port, not a vendor SDK."""

from typing import Protocol


class AudioPort(Protocol):
    def synthesize(self, text: str, lang: str = "fa") -> bytes:
        """Return audio bytes for text. Implementations (TTS vendor) plug in later."""
        ...


class NoOpAudio(AudioPort):
    def synthesize(self, text: str, lang: str = "fa") -> bytes:
        _ = (text, lang)
        return b""
