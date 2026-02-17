"""
YouTube Service - Fetch transcripts from YouTube videos.

Educational Note: This service uses the youtube-transcript-api library to fetch
existing captions/transcripts from YouTube videos. It's much faster than downloading
and transcribing audio since it uses YouTube's existing caption data.

Proxy Support: YouTube often blocks datacenter IPs (e.g., AWS). When WEBSHARE_API_KEY
is configured, the service will try fetching without a proxy first, then fallback to
rotating Webshare proxies on IP-related failures. Content errors (disabled transcripts,
private videos) are NOT retried with a proxy since they'd fail regardless.

Install: pip install youtube-transcript-api
"""

import logging
import os
import re
import time
from typing import Dict, Any, Optional, List
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
import requests as http_requests  # Aliased to avoid confusion with flask.request

logger = logging.getLogger(__name__)

# Proxy cache TTL in seconds (30 minutes)
PROXY_CACHE_TTL = 1800


class YouTubeService:
    """
    Service class for fetching YouTube video transcripts.

    Educational Note: YouTube stores transcripts as a list of snippets,
    each with text, start time, and duration. We combine these into
    readable text with optional timestamps.
    """

    # Regex patterns for extracting video ID from various YouTube URL formats
    VIDEO_ID_PATTERNS = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})',
    ]

    # Error substrings that indicate a content problem (not an IP block).
    # These should NOT be retried with a proxy — they'd fail regardless.
    CONTENT_ERROR_KEYWORDS = [
        "disabled",
        "no transcript",
        "not translatable",
        "unavailable",
        "private",
    ]

    def __init__(self):
        """Initialize the YouTube service."""
        self._api = YouTubeTranscriptApi()
        # Proxy cache state
        self._proxies: List[str] = []
        self._proxies_fetched_at: float = 0.0
        self._proxy_index: int = 0

    def extract_video_id(self, url: str) -> Optional[str]:
        """
        Extract video ID from various YouTube URL formats.

        Supported formats:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - https://youtube.com/watch?v=VIDEO_ID&other_params

        Args:
            url: YouTube URL

        Returns:
            11-character video ID or None if not found
        """
        for pattern in self.VIDEO_ID_PATTERNS:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _get_proxies(self) -> List[str]:
        """
        Fetch and cache proxy list from the Webshare API.

        Educational Note: Webshare provides rotating residential/datacenter proxies.
        We cache the list for 30 minutes to avoid hitting their API on every transcript
        request. The proxy list endpoint returns IP:port pairs that we format as URLs.

        Returns:
            List of proxy URLs like "http://user:pass@ip:port" (empty if not configured)
        """
        api_key = os.getenv("WEBSHARE_API_KEY")
        if not api_key:
            return []

        # Return cached proxies if still fresh
        if self._proxies and (time.time() - self._proxies_fetched_at) < PROXY_CACHE_TTL:
            return self._proxies

        try:
            response = http_requests.get(
                "https://proxy.webshare.io/api/v2/proxy/list/",
                headers={"Authorization": f"Token {api_key}"},
                params={"mode": "direct", "page_size": 25},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            proxies = []
            for proxy in data.get("results", []):
                # Build proxy URL: http://username:password@ip:port
                username = proxy.get("username", "")
                password = proxy.get("password", "")
                ip = proxy.get("proxy_address", "")
                port = proxy.get("port", "")
                if ip and port and username and password:
                    proxies.append(f"http://{username}:{password}@{ip}:{port}")

            self._proxies = proxies
            self._proxies_fetched_at = time.time()
            self._proxy_index = 0
            logger.info("Fetched %d proxies from Webshare", len(proxies))
            return proxies

        except Exception as e:
            logger.warning("Failed to fetch Webshare proxies: %s", e)
            # Return stale cache if available, otherwise empty
            return self._proxies

    def _get_next_proxy(self) -> Optional[str]:
        """
        Get the next proxy URL using round-robin rotation.

        Returns:
            A proxy URL string, or None if no proxies available
        """
        proxies = self._get_proxies()
        if not proxies:
            return None
        proxy = proxies[self._proxy_index % len(proxies)]
        self._proxy_index += 1
        return proxy

    def _is_content_error(self, error_msg: str) -> bool:
        """
        Check if an error is a content-level problem (not an IP block).

        Content errors like "transcripts disabled" or "video unavailable" would fail
        with any IP, so retrying through a proxy is pointless.

        Args:
            error_msg: The error message string from the transcript API

        Returns:
            True if this is a content error that should NOT be retried with a proxy
        """
        error_lower = error_msg.lower()
        return any(keyword in error_lower for keyword in self.CONTENT_ERROR_KEYWORDS)

    def get_transcript(
        self,
        url: str,
        include_timestamps: bool = False,
        preferred_languages: List[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch transcript for a YouTube video.

        Args:
            url: YouTube video URL
            include_timestamps: Whether to include timestamps in output
            preferred_languages: List of language codes to try (default: ['en'])

        Returns:
            Dict with:
                - success: bool
                - video_id: str
                - transcript: str (formatted transcript text)
                - language: str (language code of transcript)
                - is_auto_generated: bool
                - duration_seconds: float (total video duration)
                - segment_count: int
                - error_message: str (if failed)
        """
        if preferred_languages is None:
            preferred_languages = ['en']

        # Extract video ID
        video_id = self.extract_video_id(url)
        if not video_id:
            logger.error("Could not extract video ID from URL: %s", url)
            return {
                "success": False,
                "error_message": f"Could not extract video ID from URL: {url}"
            }

        logger.info("Fetching transcript for video_id=%s (languages=%s)", video_id, preferred_languages)

        # Step 1: Try fetching directly (no proxy) — saves bandwidth when it works
        try:
            transcript = self._api.fetch(video_id, languages=preferred_languages)
            return self._build_success_response(video_id, transcript, include_timestamps)

        except Exception as e:
            direct_error = str(e)
            logger.warning("Direct transcript fetch failed for %s: %s", video_id, direct_error)

            # If it's a content error (disabled, private, etc.), don't bother with proxy
            if self._is_content_error(direct_error):
                return self._build_error_response(video_id, direct_error)

        # Step 2: Fallback to proxy if available
        proxy_url = self._get_next_proxy()
        if not proxy_url:
            # No proxies configured — return the original error
            logger.info("No proxies available, returning original error for %s", video_id)
            return self._build_error_response(video_id, direct_error)

        try:
            logger.info("Retrying transcript fetch for %s via proxy", video_id)
            # Create a new API instance with proxy configuration
            proxy_config = GenericProxyConfig(https_url=proxy_url)
            proxied_api = YouTubeTranscriptApi(proxy_config=proxy_config)
            transcript = proxied_api.fetch(video_id, languages=preferred_languages)
            return self._build_success_response(video_id, transcript, include_timestamps)

        except Exception as proxy_e:
            proxy_error = str(proxy_e)
            logger.exception(
                "Proxy transcript fetch also failed for %s: %s", video_id, proxy_error
            )
            # Return the proxy error since it's the most recent attempt
            return self._build_error_response(video_id, proxy_error)

    def _build_success_response(
        self,
        video_id: str,
        transcript: Any,
        include_timestamps: bool
    ) -> Dict[str, Any]:
        """Build a success response dict from a fetched transcript."""
        snippets = transcript.snippets
        language = transcript.language_code
        is_auto_generated = transcript.is_generated

        if not snippets:
            return {
                "success": False,
                "video_id": video_id,
                "error_message": "Transcript is empty"
            }

        formatted_text = self._format_transcript(
            snippets, include_timestamps=include_timestamps
        )
        last_snippet = snippets[-1]
        total_duration = last_snippet.start + last_snippet.duration

        return {
            "success": True,
            "video_id": video_id,
            "transcript": formatted_text,
            "language": language,
            "is_auto_generated": is_auto_generated,
            "duration_seconds": total_duration,
            "segment_count": len(snippets),
        }

    def _build_error_response(self, video_id: str, error_msg: str) -> Dict[str, Any]:
        """Build an error response dict with user-friendly messages."""
        error_lower = error_msg.lower()
        if "disabled" in error_lower:
            friendly = "Transcripts are disabled for this video"
        elif "unavailable" in error_lower or "private" in error_lower:
            friendly = "Video is unavailable (private, deleted, or region-locked)"
        elif "no transcript" in error_lower:
            friendly = "No transcript available for this video"
        else:
            friendly = "Error fetching transcript. Check server logs for details."

        return {
            "success": False,
            "video_id": video_id,
            "error_message": friendly,
        }

    def _format_transcript(
        self,
        snippets: List[Any],
        include_timestamps: bool = False
    ) -> str:
        """
        Format transcript snippets into readable text.

        Args:
            snippets: List of FetchedTranscriptSnippet objects
            include_timestamps: Whether to include timestamps

        Returns:
            Formatted transcript text
        """
        if not snippets:
            return ""

        lines = []

        for snippet in snippets:
            text = snippet.text.strip() if snippet.text else ""
            if not text:
                continue

            if include_timestamps:
                timestamp = self._format_timestamp(snippet.start)
                lines.append(f"[{timestamp}] {text}")
            else:
                lines.append(text)

        # Join with spaces for cleaner reading
        if include_timestamps:
            return "\n".join(lines)
        else:
            return " ".join(lines)

    def _format_timestamp(self, seconds: float) -> str:
        """
        Format seconds into HH:MM:SS or MM:SS format.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"


# Singleton instance
youtube_service = YouTubeService()
