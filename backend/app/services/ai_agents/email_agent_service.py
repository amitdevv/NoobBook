"""
Email Agent Service - AI agent for generating HTML email templates.

Educational Note: Agentic loop pattern for multi-step creative tasks:
1. Agent plans the template structure (plan_email_template)
2. Agent generates images as needed (generate_email_image - can be called multiple times)
3. Agent writes the final HTML code (write_email_code - termination tool)
4. All tools are client tools - we execute them and update job status

Tools:
- plan_email_template: Client tool - plan structure, colors, sections
- generate_email_image: Client tool - generate images via Gemini
- write_email_code: Termination tool - write final HTML, signals completion
"""

import os
import uuid
from typing import Dict, Any, List
from datetime import datetime

from app.services.integrations.claude import claude_service
from app.services.integrations.google import imagen_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_studio_dir, get_sources_dir
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service


class EmailAgentService:
    """
    Email template generation agent with multi-step creative workflow.

    Educational Note: This agent demonstrates how AI can orchestrate
    a complex creative process: planning → image generation → code writing.
    """

    AGENT_NAME = "email_agent"
    MAX_ITERATIONS = 15  # More iterations for complex templates

    def __init__(self):
        """Initialize agent with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("email_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        """Load all 3 agent tools."""
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    # =========================================================================
    # Main Agent Execution
    # =========================================================================

    def generate_template(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = ""
    ) -> Dict[str, Any]:
        """
        Run the agent to generate an email template.

        Educational Note: The agent workflow:
        1. Get source content and direction
        2. Agent plans the template (colors, structure, sections)
        3. Agent generates images for sections that need them
        4. Agent writes the final HTML code
        5. We save everything and update job status
        """
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_email_job(
            project_id, job_id,
            status="processing",
            status_message="Starting email template generation..."
        )

        # Get source content
        source_content = self._get_source_content(project_id, source_id)

        # Build initial user message
        user_message = f"""Create a professional email template based on the following source content.

=== SOURCE CONTENT ===
{source_content}
=== END SOURCE CONTENT ===

Direction from user: {direction if direction else 'No specific direction provided - use your best judgment based on the content.'}

Please create a complete email template following the workflow:
1. Plan the template structure, colors, and sections
2. Generate any images needed (photos/illustrations only - use CSS/SVG for icons)
3. Write the final HTML code with all content and styling"""

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0
        generated_images = []  # Track generated images

        print(f"[EmailAgent] Starting (job_id: {job_id[:8]})")

        for iteration in range(1, self.MAX_ITERATIONS + 1):
            print(f"  Iteration {iteration}/{self.MAX_ITERATIONS}")

            # Call Claude API
            response = claude_service.send_message(
                messages=messages,
                system_prompt=config["system_prompt"],
                model=config["model"],
                max_tokens=config["max_tokens"],
                temperature=config["temperature"],
                tools=tools["all_tools"] if isinstance(tools, dict) else tools,
                tool_choice={"type": "any"},
                project_id=project_id
            )

            # Track token usage
            total_input_tokens += response["usage"]["input_tokens"]
            total_output_tokens += response["usage"]["output_tokens"]

            # Serialize and add assistant response to messages
            content_blocks = response.get("content_blocks", [])
            serialized_content = claude_parsing_utils.serialize_content_blocks(content_blocks)
            messages.append({"role": "assistant", "content": serialized_content})

            # Process tool calls
            tool_results = []

            for block in content_blocks:
                block_type = getattr(block, "type", None) if hasattr(block, "type") else block.get("type")

                if block_type == "tool_use":
                    tool_name = getattr(block, "name", "") if hasattr(block, "name") else block.get("name", "")
                    tool_input = getattr(block, "input", {}) if hasattr(block, "input") else block.get("input", {})
                    tool_id = getattr(block, "id", "") if hasattr(block, "id") else block.get("id", "")

                    print(f"    Tool: {tool_name}")

                    # Tool 1: Plan the template
                    if tool_name == "plan_email_template":
                        result = self._handle_plan_template(project_id, job_id, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 2: Generate image
                    elif tool_name == "generate_email_image":
                        result = self._handle_generate_image(
                            project_id, job_id, tool_input, generated_images
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 3: Write HTML code (TERMINATION)
                    elif tool_name == "write_email_code":
                        final_result = self._handle_write_code(
                            project_id, job_id, source_id, tool_input,
                            generated_images, iteration, total_input_tokens, total_output_tokens
                        )

                        print(f"  Completed in {iteration} iterations")

                        # Save execution log
                        self._save_execution(
                            project_id, execution_id, job_id, messages,
                            final_result, started_at, source_id
                        )

                        return final_result

            # Add tool results to messages
            if tool_results:
                messages.append({"role": "user", "content": tool_results})

        # Max iterations reached
        print(f"  Max iterations reached ({self.MAX_ITERATIONS})")
        error_result = {
            "success": False,
            "error_message": f"Agent reached maximum iterations ({self.MAX_ITERATIONS})",
            "iterations": self.MAX_ITERATIONS,
            "usage": {"input_tokens": total_input_tokens, "output_tokens": total_output_tokens}
        }

        studio_index_service.update_email_job(
            project_id, job_id,
            status="error",
            error_message=error_result["error_message"]
        )

        self._save_execution(
            project_id, execution_id, job_id, messages,
            error_result, started_at, source_id
        )

        return error_result

    # =========================================================================
    # Tool Handlers
    # =========================================================================

    def _handle_plan_template(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle plan_email_template tool call."""
        print(f"      Planning: {tool_input.get('template_name', 'Unnamed')}")

        # Update job with plan
        studio_index_service.update_email_job(
            project_id, job_id,
            template_name=tool_input.get("template_name"),
            template_type=tool_input.get("template_type"),
            color_scheme=tool_input.get("color_scheme"),
            sections=tool_input.get("sections"),
            layout_notes=tool_input.get("layout_notes"),
            status_message="Template planned, generating images..."
        )

        return f"Template plan saved successfully. Template name: '{tool_input.get('template_name')}', Type: {tool_input.get('template_type')}, Sections: {len(tool_input.get('sections', []))}"

    def _handle_generate_image(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]]
    ) -> str:
        """Handle generate_email_image tool call."""
        section_name = tool_input.get("section_name", "unknown")
        image_prompt = tool_input.get("image_prompt", "")
        aspect_ratio = tool_input.get("aspect_ratio", "16:9")

        print(f"      Generating image for: {section_name}")

        # Update status
        studio_index_service.update_email_job(
            project_id, job_id,
            status_message=f"Generating image for {section_name}..."
        )

        try:
            # Prepare output directory
            from pathlib import Path
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
                return f"Error generating image for {section_name}: {image_result.get('error', 'Unknown error')}"

            # Get the generated image info
            image_data = image_result["images"][0]
            filename = image_data["filename"]

            # Track generated image
            image_info = {
                "section_name": section_name,
                "filename": filename,
                "placeholder": f"IMAGE_{image_index}",
                "url": f"/api/v1/projects/{project_id}/studio/email-templates/{filename}"
            }
            generated_images.append(image_info)

            # Update job
            studio_index_service.update_email_job(
                project_id, job_id,
                images=generated_images
            )

            print(f"      Saved: {filename}")

            return f"Image generated successfully for '{section_name}'. Use placeholder '{image_info['placeholder']}' in your HTML code for this image."

        except Exception as e:
            error_msg = f"Error generating image for {section_name}: {str(e)}"
            print(f"      {error_msg}")
            return error_msg

    def _handle_write_code(
        self,
        project_id: str,
        job_id: str,
        source_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Handle write_email_code tool call (termination)."""
        html_code = tool_input.get("html_code", "")
        subject_line = tool_input.get("subject_line_suggestion", "")
        preheader_text = tool_input.get("preheader_text", "")

        print(f"      Writing HTML code ({len(html_code)} chars)")

        try:
            # Replace IMAGE_N placeholders with actual URLs
            final_html = html_code
            for image_info in generated_images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_html = final_html.replace(f'"{placeholder}"', f'"{actual_url}"')
                final_html = final_html.replace(f"'{placeholder}'", f"'{actual_url}'")

            # Save HTML file
            studio_dir = get_studio_dir(project_id)
            email_dir = os.path.join(studio_dir, "email_templates")
            os.makedirs(email_dir, exist_ok=True)

            html_filename = f"{job_id}.html"
            html_path = os.path.join(email_dir, html_filename)

            with open(html_path, "w", encoding="utf-8") as f:
                f.write(final_html)

            print(f"      Saved: {html_filename}")

            # Get job info for template_name
            job = studio_index_service.get_email_job(project_id, job_id)
            template_name = job.get("template_name", "Email Template")

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
                "images": generated_images,
                "subject_line": subject_line,
                "preheader_text": preheader_text,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error saving HTML code: {str(e)}"
            print(f"      {error_msg}")

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

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _get_source_content(self, project_id: str, source_id: str) -> str:
        """
        Get source content for the email template.

        Educational Note: Same pattern as other studio services - sample chunks
        for large sources, use full content for small sources.
        """
        try:
            from app.services.source_services import source_service

            source = source_service.get_source(project_id, source_id)
            if not source:
                return "Error: Source not found"

            # Get processed content
            sources_dir = get_sources_dir(project_id)
            processed_path = os.path.join(sources_dir, "processed", f"{source_id}.txt")

            if not os.path.exists(processed_path):
                return f"Source: {source.get('name', 'Unknown')}\n(Content not yet processed)"

            with open(processed_path, "r", encoding="utf-8") as f:
                full_content = f.read()

            # If content is small enough, use it all
            if len(full_content) < 10000:  # ~2500 tokens
                return full_content

            # For large sources, sample chunks (same logic as flash_cards_service)
            chunks_dir = os.path.join(sources_dir, "chunks", source_id)
            if not os.path.exists(chunks_dir):
                # No chunks, return truncated content
                return full_content[:10000] + "\n\n[Content truncated...]"

            # Get all chunks
            chunk_files = sorted([
                f for f in os.listdir(chunks_dir)
                if f.endswith(".txt") and f.startswith(source_id)
            ])

            if not chunk_files:
                return full_content[:10000] + "\n\n[Content truncated...]"

            # Sample up to 8 chunks evenly distributed
            max_chunks = 8
            if len(chunk_files) <= max_chunks:
                selected_chunks = chunk_files
            else:
                step = len(chunk_files) / max_chunks
                selected_chunks = [chunk_files[int(i * step)] for i in range(max_chunks)]

            # Read selected chunks
            sampled_content = []
            for chunk_file in selected_chunks:
                chunk_path = os.path.join(chunks_dir, chunk_file)
                with open(chunk_path, "r", encoding="utf-8") as f:
                    sampled_content.append(f.read())

            return "\n\n".join(sampled_content)

        except Exception as e:
            print(f"[EmailAgent] Error getting source content: {e}")
            return f"Error loading source content: {str(e)}"

    def _save_execution(
        self,
        project_id: str,
        execution_id: str,
        job_id: str,
        messages: List[Dict[str, Any]],
        result: Dict[str, Any],
        started_at: str,
        source_id: str
    ) -> None:
        """Save execution log using message_service."""
        message_service.save_agent_execution(
            project_id=project_id,
            agent_name=self.AGENT_NAME,
            execution_id=execution_id,
            task=f"Generate email template (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
email_agent_service = EmailAgentService()
