"""
TTS Service - Text-to-Speech using ElevenLabs API.

Educational Note: This service converts text to speech using ElevenLabs' TTS API.
It's used by studio services like audio overview to generate spoken content.

Key Features:
- Multiple voice options (uses default high-quality voice)
- Multiple output formats (mp3, wav)
- Multilingual support via eleven_multilingual_v2 model
- Streaming support for long content

Models:
- eleven_multilingual_v2: High quality, supports 29 languages
- eleven_turbo_v2_5: Faster, English-optimized, lower latency

Output Formats:
- mp3_44100_128: Default, good quality/size balance
- mp3_44100_192: Higher quality (Creator tier+)
- pcm_16000: Raw PCM for processing
"""
import logging
import os
from typing import Optional, Generator
from datetime import datetime

logger = logging.getLogger(__name__)


class TTSService:
    """
    Service class for text-to-speech via ElevenLabs.

    Educational Note: Uses the ElevenLabs Python SDK to convert text to audio.
    Supports both file generation and streaming for different use cases.
    """

    # Default voice - George (warm, engaging narrator voice)
    # You can find voice IDs at https://elevenlabs.io/voice-library
    DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George - warm, narrative style

    # Alternative voices for reference:
    # "21m00Tcm4TlvDq8ikWAM" - Rachel (calm, clear female)
    # "AZnzlk1XvdvUeBnXmlld" - Domi (expressive female)
    # "EXAVITQu4vr4xnSDxMaL" - Bella (soft, warm female)
    # "ErXwobaYiN019PkySvjV" - Antoni (well-rounded male)

    # Model for high-quality multilingual TTS
    DEFAULT_MODEL = "eleven_multilingual_v2"

    # Output format: codec_samplerate_bitrate
    DEFAULT_OUTPUT_FORMAT = "mp3_44100_128"

    # ElevenLabs has a 10,000 character limit per request
    # We use 9,500 to leave buffer for edge cases
    MAX_CHARS_PER_REQUEST = 9500

    def __init__(self):
        """Initialize the TTS service."""
        self._client = None

    def _get_client(self):
        """
        Get or create the ElevenLabs client.

        Returns:
            ElevenLabs client instance

        Raises:
            ValueError: If ELEVENLABS_API_KEY is not configured
        """
        if self._client is None:
            api_key = os.getenv('ELEVENLABS_API_KEY')
            if not api_key:
                raise ValueError(
                    "ELEVENLABS_API_KEY not found in environment. "
                    "Please configure it in Admin Settings."
                )

            from elevenlabs.client import ElevenLabs
            self._client = ElevenLabs(api_key=api_key)

        return self._client

    def _split_text_for_tts(self, text: str) -> list:
        """
        Split text into chunks under MAX_CHARS_PER_REQUEST at sentence boundaries.

        Educational Note: ElevenLabs has a 10k character limit. We split at
        sentence boundaries (. ! ?) to avoid cutting mid-sentence which would
        sound unnatural in the generated audio.
        """
        if len(text) <= self.MAX_CHARS_PER_REQUEST:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by sentence endings
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            # If single sentence exceeds limit, split by words
            if len(sentence) > self.MAX_CHARS_PER_REQUEST:
                # Save current chunk first
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                # Split long sentence by words
                words = sentence.split()
                for word in words:
                    if len(current_chunk) + len(word) + 1 > self.MAX_CHARS_PER_REQUEST:
                        chunks.append(current_chunk.strip())
                        current_chunk = word
                    else:
                        current_chunk = f"{current_chunk} {word}" if current_chunk else word
            # Normal case - add sentence if it fits
            elif len(current_chunk) + len(sentence) + 1 > self.MAX_CHARS_PER_REQUEST:
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                current_chunk = f"{current_chunk} {sentence}" if current_chunk else sentence

        # Add remaining content
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def generate_audio_bytes(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
        output_format: Optional[str] = None
    ) -> dict:
        """
        Generate audio from text and return bytes directly (no disk write).

        Educational Note: Generates audio and returns raw bytes directly
        instead of writing to a file. Used for Supabase Storage uploads.

        Args:
            text: The text to convert to speech
            voice_id: ElevenLabs voice ID (uses default if not specified)
            model_id: TTS model to use (uses multilingual_v2 by default)
            output_format: Audio format (uses mp3_44100_128 by default)

        Returns:
            Dict with success status and audio bytes:
            {
                "success": True,
                "audio_bytes": bytes,
                "file_size_bytes": int,
                "character_count": int,
                "word_count": int,
                "estimated_duration_seconds": float,
                "voice_id": str,
                "model_id": str,
                "output_format": str,
                "generated_at": str
            }
        """
        if not text or not text.strip():
            return {
                "success": False,
                "error": "No text provided for TTS conversion"
            }

        try:
            client = self._get_client()

            logger.info("Generating TTS audio: %s chars", len(text))

            voice = voice_id or self.DEFAULT_VOICE_ID
            model = model_id or self.DEFAULT_MODEL
            fmt = output_format or self.DEFAULT_OUTPUT_FORMAT

            # Split text if it exceeds ElevenLabs limit
            text_chunks = self._split_text_for_tts(text)

            # Generate audio for each chunk
            all_audio_bytes = []
            for i, chunk in enumerate(text_chunks, 1):
                audio_generator = client.text_to_speech.convert(
                    text=chunk,
                    voice_id=voice,
                    model_id=model,
                    output_format=fmt
                )
                chunk_bytes = b"".join(audio_generator)
                all_audio_bytes.append(chunk_bytes)

            # Combine all audio chunks (MP3 files can be concatenated directly)
            audio_bytes = b"".join(all_audio_bytes)

            # Calculate duration estimate
            word_count = len(text.split())
            estimated_duration_seconds = (word_count / 150) * 60

            logger.info("TTS audio generated: %s bytes, ~%.0fs", len(audio_bytes), estimated_duration_seconds)

            return {
                "success": True,
                "audio_bytes": audio_bytes,
                "file_size_bytes": len(audio_bytes),
                "character_count": len(text),
                "word_count": word_count,
                "estimated_duration_seconds": estimated_duration_seconds,
                "voice_id": voice,
                "model_id": model,
                "output_format": fmt,
                "generated_at": datetime.now().isoformat()
            }

        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Error generating TTS audio")
            return {"success": False, "error": f"TTS generation failed: {str(e)}"}

    def generate_audio_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> Generator[bytes, None, None]:
        """
        Generate audio stream from text.

        Educational Note: For streaming use cases where you want to start
        playing audio before the full generation is complete. Returns a
        generator that yields audio chunks.

        Args:
            text: The text to convert to speech
            voice_id: ElevenLabs voice ID (uses default if not specified)
            model_id: TTS model to use (uses multilingual_v2 by default)

        Yields:
            Audio bytes chunks
        """
        client = self._get_client()

        voice = voice_id or self.DEFAULT_VOICE_ID
        model = model_id or self.DEFAULT_MODEL

        # Use streaming endpoint
        audio_stream = client.text_to_speech.convert_as_stream(
            text=text,
            voice_id=voice,
            model_id=model
        )

        for chunk in audio_stream:
            yield chunk

    def list_voices(self) -> dict:
        """
        List available voices from ElevenLabs.

        Educational Note: Useful for letting users choose their preferred voice.
        Returns both default voices and any cloned voices in the account.

        Returns:
            Dict with success status and list of voices
        """
        try:
            client = self._get_client()

            response = client.voices.get_all()

            voices = []
            for voice in response.voices:
                voices.append({
                    "voice_id": voice.voice_id,
                    "name": voice.name,
                    "category": getattr(voice, 'category', 'unknown'),
                    "description": getattr(voice, 'description', ''),
                    "preview_url": getattr(voice, 'preview_url', None)
                })

            return {
                "success": True,
                "voices": voices,
                "count": len(voices)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "voices": []
            }

    def is_configured(self) -> bool:
        """
        Check if ElevenLabs API key is configured.

        Returns:
            True if API key is set, False otherwise
        """
        return bool(os.getenv('ELEVENLABS_API_KEY'))


# Singleton instance
tts_service = TTSService()
