"""
Imagen Service — provider-switching facade for image generation.

Default provider is OpenAI **GPT Image 2** (`gpt-image-2-2026-04-21`) via
`gpt_image_service`. If GPT Image 2 isn't usable (model not yet available
on the key, org not verified, etc.), this falls back to Google's
`gemini-3-pro-image-preview` automatically — same call shape, same
return dict — so the studio surfaces don't need to know which provider
served them.

Public surface (unchanged from before the GPT Image 2 swap):
- `is_configured() -> bool`
- `generate_image_bytes(...) -> {success, filename, image_bytes, content_type}`
- `generate_image_with_reference(...)` — multimodal (e.g. brand logo)
- `generate_images(...)` — multi-image batch (legacy, used only by ad creatives loop)

Streaming: callers may pass `on_partial(b64_json, idx)` to receive partial
image frames as they're rendered. The Gemini fallback ignores `on_partial`
since Gemini doesn't stream partials.
"""
import logging
import os
import io
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from datetime import datetime

from app.services.integrations.openai.gpt_image_service import gpt_image_service

logger = logging.getLogger(__name__)


PartialCallback = Callable[[str, int], None]


class ImagenService:
    """
    Image generation facade. Tries GPT Image 2 first, falls back to Gemini
    on model-availability errors.
    """

    MODEL_ID = "gemini-3-pro-image-preview"
    DEFAULT_ASPECT_RATIO = "9:16"
    DEFAULT_RESOLUTION = "1K"

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 2

    def __init__(self):
        self._client = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def is_configured(self) -> bool:
        """True if either provider is configured."""
        return gpt_image_service.is_configured() or bool(os.getenv("NANO_BANANA_API_KEY"))

    def _gemini_configured(self) -> bool:
        return bool(os.getenv("NANO_BANANA_API_KEY"))

    # ------------------------------------------------------------------
    # Public API — provider switching happens here
    # ------------------------------------------------------------------

    def generate_image_bytes(
        self,
        prompt: str,
        filename_prefix: str = "image",
        aspect_ratio: str = None,
        resolution: str = None,
        *,
        quality: str = "medium",
        project_id: Optional[str] = None,
        on_partial: Optional[PartialCallback] = None,
    ) -> Dict[str, Any]:
        if gpt_image_service.is_configured():
            result = gpt_image_service.generate_image_bytes(
                prompt=prompt,
                filename_prefix=filename_prefix,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                quality=quality,
                project_id=project_id,
                on_partial=on_partial,
            )
            if result.get("success"):
                return result
            if not result.get("fallback_to_gemini"):
                return result
            logger.warning(
                "GPT Image 2 unavailable (%s) — falling back to Gemini",
                result.get("error"),
            )
        return self._gemini_generate_image_bytes(
            prompt, filename_prefix, aspect_ratio, resolution,
        )

    def generate_image_with_reference(
        self,
        prompt: str,
        reference_image_bytes: bytes,
        reference_mime_type: str = "image/png",
        filename_prefix: str = "image",
        aspect_ratio: str = None,
        resolution: str = None,
        *,
        quality: str = "medium",
        project_id: Optional[str] = None,
        on_partial: Optional[PartialCallback] = None,
    ) -> Dict[str, Any]:
        if gpt_image_service.is_configured():
            result = gpt_image_service.generate_image_with_reference(
                prompt=prompt,
                reference_image_bytes=reference_image_bytes,
                reference_mime_type=reference_mime_type,
                filename_prefix=filename_prefix,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                quality=quality,
                project_id=project_id,
                on_partial=on_partial,
            )
            if result.get("success"):
                return result
            if not result.get("fallback_to_gemini"):
                return result
            logger.warning(
                "GPT Image 2 edit unavailable (%s) — falling back to Gemini",
                result.get("error"),
            )
        return self._gemini_generate_image_with_reference(
            prompt, reference_image_bytes, reference_mime_type,
            filename_prefix, aspect_ratio, resolution,
        )

    def generate_images(
        self,
        prompt: str,
        output_dir: Path,
        num_images: int = 3,
        filename_prefix: str = "creative",
        aspect_ratio: str = None,
        resolution: str = None,
    ) -> Dict[str, Any]:
        # Multi-image disk-write path is only used by legacy callers; we
        # don't bother streaming it. Try GPT Image 2 sequentially and
        # fall through to Gemini on any unavailability.
        if gpt_image_service.is_configured():
            num_images = min(num_images, 3)
            aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO
            resolution = resolution or self.DEFAULT_RESOLUTION
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            image_paths = []
            for i in range(num_images):
                result = gpt_image_service.generate_image_bytes(
                    prompt=prompt,
                    filename_prefix=f"{filename_prefix}_{i+1}",
                    aspect_ratio=aspect_ratio,
                    resolution=resolution,
                )
                if not result.get("success"):
                    if result.get("fallback_to_gemini"):
                        logger.warning("GPT Image 2 unavailable mid-batch — falling back to Gemini for the whole batch")
                        return self._gemini_generate_images(
                            prompt, output_dir, num_images, filename_prefix, aspect_ratio, resolution,
                        )
                    return {"success": False, "error": result.get("error", "image generation failed")}

                filename = f"{filename_prefix}_{timestamp}_{i+1}.png"
                filepath = output_dir / filename
                with open(filepath, "wb") as f:
                    f.write(result["image_bytes"])
                image_paths.append({
                    "filename": filename,
                    "path": str(filepath),
                    "index": i + 1,
                })

            return {
                "success": True,
                "images": image_paths,
                "count": len(image_paths),
                "prompt": prompt,
                "model": gpt_image_service.MODEL_ID,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "generated_at": datetime.now().isoformat(),
            }
        return self._gemini_generate_images(
            prompt, output_dir, num_images, filename_prefix, aspect_ratio, resolution,
        )

    # ------------------------------------------------------------------
    # Gemini provider — preserved as private methods
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._client is None:
            api_key = os.getenv("NANO_BANANA_API_KEY")
            if not api_key:
                raise ValueError(
                    "NANO_BANANA_API_KEY not found in environment. "
                    "Please configure it in Admin Settings."
                )
            from google import genai
            self._client = genai.Client(api_key=api_key)
        return self._client

    def _get_types(self):
        from google.genai import types
        return types

    def _is_transient_error(self, error: Exception) -> bool:
        from google.genai.errors import ServerError, ClientError
        if isinstance(error, ServerError):
            return True
        if isinstance(error, ClientError) and getattr(error, "code", None) == 429:
            return True
        return False

    def _call_with_retry(self, api_call, description: str = "API call"):
        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return api_call()
            except Exception as e:
                last_error = e
                if not self._is_transient_error(e) or attempt == self.MAX_RETRIES:
                    raise
                delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "%s failed (attempt %d/%d), retrying in %ds: %s",
                    description, attempt + 1, self.MAX_RETRIES + 1, delay, e,
                )
                time.sleep(delay)
        raise last_error

    def _gemini_generate_images(
        self,
        prompt: str,
        output_dir: Path,
        num_images: int = 3,
        filename_prefix: str = "creative",
        aspect_ratio: str = None,
        resolution: str = None,
    ) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No prompt provided for image generation"}

        num_images = min(num_images, 3)
        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO
        resolution = resolution or self.DEFAULT_RESOLUTION

        try:
            client = self._get_client()
            types = self._get_types()
            output_dir.mkdir(parents=True, exist_ok=True)
            image_paths = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for i in range(num_images):
                response = self._call_with_retry(
                    lambda: client.models.generate_content(
                        model=self.MODEL_ID,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                            image_config=types.ImageConfig(
                                aspect_ratio=aspect_ratio,
                                image_size=resolution,
                            ),
                        ),
                    ),
                    description=f"Gemini image {i+1}/{num_images}",
                )
                for part in response.parts:
                    if part.text is not None:
                        pass
                    elif (image := part.as_image()):
                        filename = f"{filename_prefix}_{timestamp}_{i+1}.png"
                        filepath = output_dir / filename
                        image.save(str(filepath))
                        image_paths.append({"filename": filename, "path": str(filepath), "index": i + 1})
                        break

            if not image_paths:
                return {"success": False, "error": "No images generated by the API"}

            return {
                "success": True,
                "images": image_paths,
                "count": len(image_paths),
                "prompt": prompt,
                "model": self.MODEL_ID,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "generated_at": datetime.now().isoformat(),
            }
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Error generating images via Gemini")
            return {"success": False, "error": f"Image generation failed: {str(e)}"}

    def _gemini_generate_image_bytes(
        self,
        prompt: str,
        filename_prefix: str = "image",
        aspect_ratio: str = None,
        resolution: str = None,
    ) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No prompt provided for image generation"}

        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO
        resolution = resolution or self.DEFAULT_RESOLUTION

        try:
            client = self._get_client()
            types = self._get_types()
            response = self._call_with_retry(
                lambda: client.models.generate_content(
                    model=self.MODEL_ID,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                            image_size=resolution,
                        ),
                    ),
                ),
                description="Gemini single image",
            )

            for part in response.parts:
                if part.text is not None:
                    pass
                elif (image := part.as_image()):
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp_path = tmp.name
                    try:
                        image.save(tmp_path)
                        with open(tmp_path, "rb") as f:
                            img_bytes = f.read()
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    return {
                        "success": True,
                        "filename": f"{filename_prefix}_{timestamp}.png",
                        "image_bytes": img_bytes,
                        "content_type": "image/png",
                    }
            return {"success": False, "error": "No image generated by the API"}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Error generating image via Gemini")
            return {"success": False, "error": f"Image generation failed: {str(e)}"}

    def _gemini_generate_image_with_reference(
        self,
        prompt: str,
        reference_image_bytes: bytes,
        reference_mime_type: str = "image/png",
        filename_prefix: str = "image",
        aspect_ratio: str = None,
        resolution: str = None,
    ) -> Dict[str, Any]:
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No prompt provided for image generation"}

        aspect_ratio = aspect_ratio or self.DEFAULT_ASPECT_RATIO
        resolution = resolution or self.DEFAULT_RESOLUTION

        try:
            client = self._get_client()
            types = self._get_types()
            contents = [
                types.Part.from_bytes(
                    data=reference_image_bytes, mime_type=reference_mime_type,
                ),
                prompt,
            ]
            response = client.models.generate_content(
                model=self.MODEL_ID,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio,
                        image_size=resolution,
                    ),
                ),
            )

            for part in response.parts:
                if part.text is not None:
                    pass
                elif (image := part.as_image()):
                    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                        tmp_path = tmp.name
                    try:
                        image.save(tmp_path)
                        with open(tmp_path, "rb") as f:
                            img_bytes = f.read()
                    finally:
                        if os.path.exists(tmp_path):
                            os.remove(tmp_path)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    return {
                        "success": True,
                        "filename": f"{filename_prefix}_{timestamp}.png",
                        "image_bytes": img_bytes,
                        "content_type": "image/png",
                    }
            return {"success": False, "error": "No image generated by the API"}
        except ValueError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.exception("Error generating image with reference via Gemini")
            return {"success": False, "error": f"Image generation failed: {str(e)}"}


imagen_service = ImagenService()
