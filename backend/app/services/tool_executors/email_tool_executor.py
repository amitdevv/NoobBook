"""
Email Tool Executor - Handles tool execution for email agent.

Tool handlers extracted from email_agent_service.py for separation of concerns.
Agent handles orchestration, executor handles tool-specific logic.
"""

import logging
import os
import re
from typing import Dict, Any, Tuple, List
from datetime import datetime
from pathlib import Path

from app.utils.path_utils import get_studio_dir
from app.services.studio_services import studio_index_service
from app.services.integrations.google import imagen_service

logger = logging.getLogger(__name__)


class EmailToolExecutor:
    """Executes email agent tools."""

    TERMINATION_TOOL = "write_email_code"

    def execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Execute a tool and return result.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters from Claude
            context: Execution context (project_id, job_id, generated_images, etc.)

        Returns:
            Tuple of (result_dict, is_termination)
        """
        project_id = context["project_id"]
        job_id = context["job_id"]

        if tool_name == "plan_email_template":
            brand_colors = context.get("brand_colors")
            result = self._handle_plan(project_id, job_id, tool_input, brand_colors)
            return {"success": True, "message": result}, False

        elif tool_name == "generate_email_image":
            generated_images = context.get("generated_images", [])
            result, image_info = self._handle_generate_image(
                project_id, job_id, tool_input, generated_images
            )
            # Append brand color reminder after image generation since this is
            # typically the last step before write_email_code — reinforces the
            # exact hex values right before the agent writes HTML.
            brand_colors = context.get("brand_colors")
            if brand_colors and result:
                result += (
                    f" REMINDER: Use brand colors in HTML — "
                    f"primary={brand_colors.get('primary')}, "
                    f"button/CTA={brand_colors.get('accent')}, "
                    f"background={brand_colors.get('background')}, "
                    f"text={brand_colors.get('text')}."
                )
            return {"success": True, "message": result, "image_info": image_info}, False

        elif tool_name == "write_email_code":
            result = self._handle_write_code(
                project_id=project_id,
                job_id=job_id,
                tool_input=tool_input,
                generated_images=context.get("generated_images", []),
                logo_info=context.get("logo_info"),
                iterations=context.get("iterations", 0),
                input_tokens=context.get("input_tokens", 0),
                output_tokens=context.get("output_tokens", 0)
            )
            return result, True  # Termination

        else:
            return {"success": False, "message": f"Unknown tool: {tool_name}"}, False

    def _handle_plan(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        brand_colors: Dict[str, Any] = None
    ) -> str:
        """
        Handle plan_email_template tool call.

        Educational Note: Prompt-based reminders proved unreliable — the agent
        would acknowledge brand colors but still generate HTML with generic ones.
        Now we hard-override the planned color_scheme with brand values, so even
        if the agent ignores instructions, the stored plan has correct colors.
        The tool result also tells the agent exactly which hex values to use.
        """
        template_name = tool_input.get("template_name", "Unnamed")
        template_type = tool_input.get("template_type")
        sections = tool_input.get("sections", [])


        result = (
            f"Template plan saved successfully. "
            f"Template name: '{template_name}', "
            f"Type: {template_type}, "
            f"Sections: {len(sections)}"
        )

        # Hard-override planned colors with brand palette
        if brand_colors:
            planned_scheme = tool_input.get("color_scheme", {})
            corrected_scheme = {
                "primary": brand_colors.get("primary", planned_scheme.get("primary", "#000000")),
                "secondary": brand_colors.get("secondary", planned_scheme.get("secondary", "#666666")),
                "background": brand_colors.get("background", planned_scheme.get("background", "#FFFFFF")),
                "text": brand_colors.get("text", planned_scheme.get("text", "#1A1A1A")),
                "button": brand_colors.get("accent", planned_scheme.get("button", "#0066CC")),
            }
            tool_input["color_scheme"] = corrected_scheme
            result += (
                f" NOTE: Your color_scheme has been corrected to match brand guidelines: "
                f"primary={corrected_scheme['primary']}, secondary={corrected_scheme['secondary']}, "
                f"button={corrected_scheme['button']}, background={corrected_scheme['background']}, "
                f"text={corrected_scheme['text']}. Use these EXACT hex values in the HTML."
            )

        # Update job with plan (uses corrected color_scheme if brand was active)
        studio_index_service.update_email_job(
            project_id, job_id,
            template_name=template_name,
            template_type=template_type,
            color_scheme=tool_input.get("color_scheme"),
            sections=sections,
            layout_notes=tool_input.get("layout_notes"),
            status_message="Template planned, generating images..."
        )

        return result

    def _handle_generate_image(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]]
    ) -> Tuple[str, Dict[str, str]]:
        """
        Handle generate_email_image tool call.

        Returns:
            Tuple of (result_message, image_info_dict or None)
        """
        section_name = tool_input.get("section_name", "unknown")
        image_prompt = tool_input.get("image_prompt", "")
        aspect_ratio = tool_input.get("aspect_ratio", "16:9")


        # Update status
        studio_index_service.update_email_job(
            project_id, job_id,
            status_message=f"Generating image for {section_name}..."
        )

        try:
            # Prepare output directory
            studio_dir = get_studio_dir(project_id)
            email_dir = Path(studio_dir) / "email_templates"
            email_dir.mkdir(parents=True, exist_ok=True)

            # Create filename prefix
            image_index = len(generated_images) + 1
            filename_prefix = f"{job_id}_image_{image_index}"

            # Generate image via Gemini
            image_result = imagen_service.generate_images(
                prompt=image_prompt,
                output_dir=email_dir,
                num_images=1,
                filename_prefix=filename_prefix,
                aspect_ratio=aspect_ratio
            )

            if not image_result.get("success") or not image_result.get("images"):
                image_index = len(generated_images) + 1
                placeholder = f"IMAGE_{image_index}"
                error_msg = (
                    f"Image generation failed for '{section_name}': "
                    f"{image_result.get('error', 'Unknown error')}. "
                    f"Do NOT use placeholder '{placeholder}' in your HTML. "
                    f"Instead, use a CSS gradient or solid brand-color background for that section."
                )
                return error_msg, None

            # Get the generated image info
            image_data = image_result["images"][0]
            filename = image_data["filename"]

            # Build image info
            image_info = {
                "section_name": section_name,
                "filename": filename,
                "placeholder": f"IMAGE_{image_index}",
                "url": f"/api/v1/projects/{project_id}/studio/email-templates/{filename}"
            }

            # Update job with new image list
            updated_images = generated_images + [image_info]
            studio_index_service.update_email_job(
                project_id, job_id,
                images=updated_images
            )

            result_msg = (
                f"Image generated successfully for '{section_name}'. "
                f"Use placeholder '{image_info['placeholder']}' in your HTML code for this image."
            )
            return result_msg, image_info

        except Exception as e:
            image_index = len(generated_images) + 1
            placeholder = f"IMAGE_{image_index}"
            error_msg = (
                f"Image generation failed for '{section_name}': {str(e)}. "
                f"Do NOT use placeholder '{placeholder}' in your HTML. "
                f"Instead, use a CSS gradient or solid brand-color background for that section."
            )
            logger.exception("Email image generation failed for %s", section_name)
            return error_msg, None

    def _handle_write_code(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]],
        logo_info: Dict[str, str] = None,
        iterations: int = 0,
        input_tokens: int = 0,
        output_tokens: int = 0
    ) -> Dict[str, Any]:
        """Handle write_email_code tool call (termination)."""
        html_code = tool_input.get("html_code", "")
        subject_line = tool_input.get("subject_line_suggestion", "")
        preheader_text = tool_input.get("preheader_text", "")


        try:
            # Replace IMAGE_N placeholders with actual URLs
            final_html = html_code
            for image_info in generated_images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_html = final_html.replace(f'"{placeholder}"', f'"{actual_url}"')
                final_html = final_html.replace(f"'{placeholder}'", f"'{actual_url}'")

            # Safety net: remove any <img> tags with unreplaced IMAGE_N placeholders.
            # This catches cases where image generation failed but the agent still
            # used the placeholder despite being told not to.
            final_html, stripped_count = re.subn(
                r'<img\s[^>]*src=["\']IMAGE_\d+["\'][^>]*/?>',
                '',
                final_html
            )
            if stripped_count > 0:
                logger.warning("Removed %s unreplaced IMAGE_N placeholder(s) from HTML", stripped_count)

            # Replace BRAND_LOGO placeholder with actual logo URL
            if logo_info:
                logo_url = logo_info["url"]
                final_html = final_html.replace('"BRAND_LOGO"', f'"{logo_url}"')
                final_html = final_html.replace("'BRAND_LOGO'", f"'{logo_url}'")

                # Fallback: inject logo if agent didn't include it at all.
                # Educational Note: Even with user-message brand instructions, Claude
                # sometimes omits the logo <img> tag entirely. This guarantees the
                # brand logo appears in the email header regardless.
                if logo_url not in final_html:
                    logo_img = (
                        f'<tr><td align="center" style="padding:20px 0;background:transparent;">'
                        f'<img src="{logo_url}" alt="Logo" '
                        f'style="max-height:60px;width:auto;display:block;"></td></tr>'
                    )
                    # Insert after the first 600px-wide table (the main email container),
                    # falling back to right after <body> for responsive/non-standard layouts.
                    body_table_match = re.search(r'(<table[^>]*width="600"[^>]*>)', final_html)
                    if body_table_match:
                        insert_pos = body_table_match.end()
                        final_html = final_html[:insert_pos] + logo_img + final_html[insert_pos:]
                        logger.info("Logo injected (agent omitted BRAND_LOGO placeholder)")
                    else:
                        body_match = re.search(r'(<body[^>]*>)', final_html, re.IGNORECASE)
                        if body_match:
                            insert_pos = body_match.end()
                            final_html = final_html[:insert_pos] + logo_img + final_html[insert_pos:]
                            logger.info("Logo injected after <body> (no 600px table found)")
                        else:
                            logger.warning("Could not inject brand logo — no <body> or 600px table found")

            # Save HTML file
            studio_dir = get_studio_dir(project_id)
            email_dir = os.path.join(studio_dir, "email_templates")
            os.makedirs(email_dir, exist_ok=True)

            html_filename = f"{job_id}.html"
            html_path = os.path.join(email_dir, html_filename)

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(final_html)

            # Get job info for template_name
            job = studio_index_service.get_email_job(project_id, job_id)
            template_name = job.get("template_name", "Email Template") if job else "Email Template"

            # Include brand logo in the images list for ZIP download
            all_images = list(generated_images)
            if logo_info:
                all_images.append(logo_info)

            # Update job to ready
            studio_index_service.update_email_job(
                project_id, job_id,
                status="ready",
                status_message="Email template generated successfully!",
                html_file=html_filename,
                html_url=f"/api/v1/projects/{project_id}/studio/email-templates/{html_filename}",
                preview_url=f"/api/v1/projects/{project_id}/studio/email-templates/{job_id}/preview",
                subject_line=subject_line,
                preheader_text=preheader_text,
                images=all_images,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "template_name": template_name,
                "html_file": html_filename,
                "html_url": f"/api/v1/projects/{project_id}/studio/email-templates/{html_filename}",
                "preview_url": f"/api/v1/projects/{project_id}/studio/email-templates/{job_id}/preview",
                "images": all_images,
                "subject_line": subject_line,
                "preheader_text": preheader_text,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error saving HTML code: {str(e)}"
            logger.exception("Failed to save email HTML")

            studio_index_service.update_email_job(
                project_id, job_id,
                status="error",
                error_message=error_msg
            )

            return {
                "success": False,
                "error_message": error_msg,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }


# Singleton instance
email_tool_executor = EmailToolExecutor()
