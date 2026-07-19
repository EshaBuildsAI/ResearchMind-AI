"""
voice_service.py
Voice Research Assistant — speech-to-text (Whisper) and text-to-speech (TTS)
via the OpenAI API.

Honest note: the pinned Streamlit version doesn't include the newer
st.audio_input microphone widget, so this works via audio FILE upload —
record a voice memo on your phone/laptop and upload it, rather than
recording live in the browser. Still a real voice pipeline, just not
live-mic — documented here rather than silently pretending otherwise.
"""

import io

from ai_services import _get_client
from constants import WHISPER_MODEL, TTS_MODEL, TTS_VOICE
from logger import log_error, log_info


def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Convert spoken audio to text using OpenAI Whisper."""
    client = _get_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename  # the OpenAI SDK needs a filename to detect format

    try:
        transcript = client.audio.transcriptions.create(
            model=WHISPER_MODEL,
            file=audio_file,
        )
        log_info("Audio transcribed successfully")
        return transcript.text.strip()
    except Exception as e:
        log_error("Audio transcription failed", e)
        raise


def generate_speech(text: str) -> bytes:
    """Convert text to spoken audio using OpenAI TTS. Returns MP3 bytes.
    Input is capped at 4000 characters (the API's own limit)."""
    client = _get_client()
    try:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=text[:4000],
        )
        log_info("Speech generated successfully")
        return response.content
    except Exception as e:
        log_error("Speech generation failed", e)
        raise
