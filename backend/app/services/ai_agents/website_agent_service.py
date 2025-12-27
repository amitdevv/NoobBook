"""
Website Agent Service - AI agent for generating complete websites.

Educational Note: Agentic loop pattern with file operations for multi-file websites:
1. Agent plans the website structure (plan_website)
2. Agent generates images as needed (generate_website_image - multiple calls)
3. Agent creates files iteratively (create_file, read_file, update_file_lines, insert_code)
4. Agent can work in any order - HTML first, CSS first, or iteratively
5. Agent finalizes when complete (finalize_website - termination tool)

Tools:
- plan_website: Client tool - plan structure, pages, features, design
- generate_website_image: Client tool - generate images via Gemini
- read_file: Client tool - read files with smart context
- create_file: Client tool - create new files or overwrite existing
- update_file_lines: Client tool - replace specific line range
- insert_code: Client tool - insert code at specific position
- finalize_website: Termination tool - signals completion
"""

import os
import uuid
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

from app.services.integrations.claude import claude_service
from app.services.integrations.google import imagen_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_studio_dir, get_sources_dir
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service


class WebsiteAgentService:
    """
    Website generation agent with multi-step file operations workflow.

    Educational Note: This agent demonstrates complex file management:
    - Multi-file generation (HTML, CSS, JS)
    - Incremental file building (create → read → update → insert)
    - Context-aware file reading (smart line range handling)
    - Iterative refinement (agent can modify files multiple times)
    """

    AGENT_NAME = "website_agent"
    MAX_ITERATIONS = 30  # More iterations for complex multi-file websites

    def __init__(self):
        """Initialize agent with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("website_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        """Load all 7 agent tools."""
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    # =========================================================================
    # Main Agent Execution
    # =========================================================================

    def generate_website(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = ""
    ) -> Dict[str, Any]:
        """
        Run the agent to generate a website.

        Educational Note: The agent workflow:
        1. Get source content and direction
        2. Agent plans the website (pages, features, design)
        3. Agent generates images for photos/illustrations
        4. Agent creates files iteratively (any order)
        5. Agent can read, update, insert code as needed
        6. Agent finalizes when all files are complete
        7. We save everything and update job status
        """
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_website_job(
            project_id, job_id,
            status="processing",
            status_message="Starting website generation..."
        )

        # Get source content
        source_content = self._get_source_content(project_id, source_id)

        # Build initial user message
        user_message = f"""Create a professional website based on the following source content.

=== SOURCE CONTENT ===
{source_content}
=== END SOURCE CONTENT ===

Direction from user: {direction if direction else 'No specific direction provided - use your best judgment based on the content.'}

Please create a complete website following the workflow:
1. Plan the website structure, pages, features, and design system
2. Generate any images needed (photos/illustrations only - use CSS/SVG for icons)
3. Create all files iteratively (HTML pages, CSS, JS) - you can work in any order
4. Use read_file, update_file_lines, and insert_code to refine as needed
5. Ensure navigation and footer are consistent across all pages
6. Finalize when all files are complete and production-ready"""

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0
        generated_images = []  # Track generated images
        created_files = []  # Track created files

        print(f"[WebsiteAgent] Starting (job_id: {job_id[:8]})")

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

                    # Tool 1: Plan the website
                    if tool_name == "plan_website":
                        result = self._handle_plan_website(project_id, job_id, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 2: Generate image
                    elif tool_name == "generate_website_image":
                        result = self._handle_generate_image(
                            project_id, job_id, tool_input, generated_images
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 3: Read file
                    elif tool_name == "read_file":
                        result = self._handle_read_file(
                            project_id, job_id, tool_input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 4: Create file
                    elif tool_name == "create_file":
                        result = self._handle_create_file(
                            project_id, job_id, tool_input, created_files
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 5: Update file lines
                    elif tool_name == "update_file_lines":
                        result = self._handle_update_file_lines(
                            project_id, job_id, tool_input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 6: Insert code
                    elif tool_name == "insert_code":
                        result = self._handle_insert_code(
                            project_id, job_id, tool_input
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 7: Finalize website (TERMINATION)
                    elif tool_name == "finalize_website":
                        final_result = self._handle_finalize_website(
                            project_id, job_id, source_id, tool_input,
                            generated_images, created_files, iteration,
                            total_input_tokens, total_output_tokens
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

        studio_index_service.update_website_job(
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

    def _handle_plan_website(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle plan_website tool call."""
        site_name = tool_input.get("site_name", "Unnamed Website")
        pages = tool_input.get("pages", [])

        print(f"      Planning: {site_name} ({len(pages)} pages)")

        # Update job with plan
        studio_index_service.update_website_job(
            project_id, job_id,
            site_type=tool_input.get("site_type"),
            site_name=site_name,
            pages=pages,
            features=tool_input.get("features"),
            design_system=tool_input.get("design_system"),
            navigation_style=tool_input.get("navigation_style"),
            images_needed=tool_input.get("images_needed", []),
            layout_notes=tool_input.get("layout_notes"),
            status_message=f"Planned {len(pages)}-page website, generating images..."
        )

        return f"Website plan saved successfully. Site: '{site_name}', Type: {tool_input.get('site_type')}, Pages: {len(pages)}, Features: {len(tool_input.get('features', []))}"

    def _handle_generate_image(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]]
    ) -> str:
        """Handle generate_website_image tool call."""
        purpose = tool_input.get("purpose", "unknown")
        image_prompt = tool_input.get("image_prompt", "")
        aspect_ratio = tool_input.get("aspect_ratio", "16:9")

        print(f"      Generating image for: {purpose}")

        # Update status
        studio_index_service.update_website_job(
            project_id, job_id,
            status_message=f"Generating image for {purpose}..."
        )

        try:
            # Prepare output directory
            studio_dir = get_studio_dir(project_id)
            website_dir = Path(studio_dir) / "websites" / job_id / "assets"
            website_dir.mkdir(parents=True, exist_ok=True)

            # Create filename prefix
            image_index = len(generated_images) + 1
            filename_prefix = f"{job_id}_image_{image_index}"

            # Generate image via Gemini
            image_result = imagen_service.generate_images(
                prompt=image_prompt,
                output_dir=website_dir,
                num_images=1,
                filename_prefix=filename_prefix,
                aspect_ratio=aspect_ratio
            )

            if not image_result.get("success") or not image_result.get("images"):
                return f"Error generating image for {purpose}: {image_result.get('error', 'Unknown error')}"

            # Get the generated image info
            image_data = image_result["images"][0]
            filename = image_data["filename"]

            # Track generated image
            image_info = {
                "purpose": purpose,
                "filename": filename,
                "placeholder": f"IMAGE_{image_index}",
                "url": f"/api/v1/projects/{project_id}/studio/websites/{job_id}/assets/{filename}"
            }
            generated_images.append(image_info)

            # Update job
            studio_index_service.update_website_job(
                project_id, job_id,
                images=generated_images
            )

            print(f"      Saved: {filename}")

            return f"Image generated successfully for '{purpose}'. Use placeholder '{image_info['placeholder']}' in your HTML code for this image."

        except Exception as e:
            error_msg = f"Error generating image for {purpose}: {str(e)}"
            print(f"      {error_msg}")
            return error_msg

    def _handle_read_file(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle read_file tool call with smart context awareness."""
        filename = tool_input.get("filename")
        start_line = tool_input.get("start_line")
        end_line = tool_input.get("end_line")

        print(f"      Reading: {filename}" + (f" (lines {start_line}-{end_line})" if start_line else ""))

        # Get file path
        website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
        file_path = website_dir / filename

        if not file_path.exists():
            return f"Error: File '{filename}' does not exist yet. Use create_file to create it first."

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            total_lines = len(lines)

            # Small file: return all
            if total_lines < 100:
                content = "".join(lines)
                return f"File: {filename} ({total_lines} lines)\n\n{content}"

            # Large file, no range: return overview
            if start_line is None:
                first_50 = "".join(lines[:50])
                last_50 = "".join(lines[-50:])
                omitted_count = total_lines - 100
                return f"File: {filename} ({total_lines} lines)\n\n[Lines 1-50]\n{first_50}\n\n... [{omitted_count} lines omitted] ...\n\n[Lines {total_lines-49}-{total_lines}]\n{last_50}"

            # Specific range with context
            context_start = max(0, start_line - 1 - 5)  # -1 for 0-indexing, -5 for context
            context_end = min(total_lines, (end_line if end_line else total_lines) + 5)

            content = "".join(lines[context_start:context_end])
            return f"File: {filename} (lines {context_start+1}-{context_end} of {total_lines})\n\n{content}"

        except Exception as e:
            return f"Error reading file '{filename}': {str(e)}"

    def _handle_create_file(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any],
        created_files: List[str]
    ) -> str:
        """Handle create_file tool call."""
        filename = tool_input.get("filename")
        content = tool_input.get("content", "")

        print(f"      Creating: {filename} ({len(content)} chars)")

        try:
            # Create directory if needed
            website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
            website_dir.mkdir(parents=True, exist_ok=True)

            file_path = website_dir / filename

            # Replace IMAGE_N placeholders with actual URLs
            final_content = content
            # Get images from job
            job = studio_index_service.get_website_job(project_id, job_id)
            images = job.get("images", [])
            for image_info in images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_content = final_content.replace(f'"{placeholder}"', f'"{actual_url}"')
                final_content = final_content.replace(f"'{placeholder}'", f"'{actual_url}'")
                final_content = final_content.replace(f'src={placeholder}', f'src="{actual_url}"')

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(final_content)

            line_count = len(final_content.split('\n'))
            char_count = len(final_content)

            # Track created file
            if filename not in created_files:
                created_files.append(filename)

            # Update job
            studio_index_service.update_website_job(
                project_id, job_id,
                files=created_files,
                status_message=f"Created {filename} ({len(created_files)} files so far)"
            )

            print(f"      Saved: {filename}")

            return f"File '{filename}' created successfully ({line_count} lines, {char_count} characters)"

        except Exception as e:
            return f"Error creating file '{filename}': {str(e)}"

    def _handle_update_file_lines(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle update_file_lines tool call."""
        filename = tool_input.get("filename")
        start_line = tool_input.get("start_line")
        end_line = tool_input.get("end_line")
        new_content = tool_input.get("new_content", "")

        print(f"      Updating: {filename} lines {start_line}-{end_line}")

        # Get file path
        website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
        file_path = website_dir / filename

        if not file_path.exists():
            return f"Error: File '{filename}' does not exist. Use create_file first."

        try:
            # Read existing file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Validate line numbers
            if start_line < 1 or end_line > len(lines):
                return f"Error: Invalid line range. File has {len(lines)} lines, you requested {start_line}-{end_line}."

            # Replace IMAGE_N placeholders in new content
            final_new_content = new_content
            job = studio_index_service.get_website_job(project_id, job_id)
            images = job.get("images", [])
            for image_info in images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_new_content = final_new_content.replace(f'"{placeholder}"', f'"{actual_url}"')
                final_new_content = final_new_content.replace(f"'{placeholder}'", f"'{actual_url}'")
                final_new_content = final_new_content.replace(f'src={placeholder}', f'src="{actual_url}"')

            # Replace lines (convert to 0-indexed)
            new_lines = final_new_content.split('\n')
            lines[start_line-1:end_line] = [line + '\n' for line in new_lines]

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            return f"Updated lines {start_line}-{end_line} in '{filename}'"

        except Exception as e:
            return f"Error updating file '{filename}': {str(e)}"

    def _handle_insert_code(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle insert_code tool call."""
        filename = tool_input.get("filename")
        after_line = tool_input.get("after_line")
        content = tool_input.get("content", "")

        print(f"      Inserting: {filename} after line {after_line}")

        # Get file path
        website_dir = Path(get_studio_dir(project_id)) / "websites" / job_id
        file_path = website_dir / filename

        if not file_path.exists():
            return f"Error: File '{filename}' does not exist. Use create_file first."

        try:
            # Read existing file
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Validate line number
            if after_line < 0 or after_line > len(lines):
                return f"Error: Invalid line number. File has {len(lines)} lines, you requested to insert after line {after_line}."

            # Replace IMAGE_N placeholders in content
            final_content = content
            job = studio_index_service.get_website_job(project_id, job_id)
            images = job.get("images", [])
            for image_info in images:
                placeholder = image_info["placeholder"]
                actual_url = image_info["url"]
                final_content = final_content.replace(f'"{placeholder}"', f'"{actual_url}"')
                final_content = final_content.replace(f"'{placeholder}'", f"'{actual_url}'")
                final_content = final_content.replace(f'src={placeholder}', f'src="{actual_url}"')

            # Insert new lines
            new_lines = [line + '\n' for line in final_content.split('\n')]
            lines[after_line:after_line] = new_lines

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

            return f"Inserted {len(new_lines)} lines after line {after_line} in '{filename}'"

        except Exception as e:
            return f"Error inserting code in '{filename}': {str(e)}"

    def _handle_finalize_website(
        self,
        project_id: str,
        job_id: str,
        source_id: str,
        tool_input: Dict[str, Any],
        generated_images: List[Dict[str, str]],
        created_files: List[str],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Handle finalize_website tool call (termination)."""
        summary = tool_input.get("summary", "")
        pages_created = tool_input.get("pages_created", [])
        features_implemented = tool_input.get("features_implemented", [])
        cdn_libraries = tool_input.get("cdn_libraries_used", [])

        print(f"      Finalizing website ({len(pages_created)} pages)")

        try:
            # Get job info for site_name
            job = studio_index_service.get_website_job(project_id, job_id)
            site_name = job.get("site_name", "Website")

            # Update job to ready
            studio_index_service.update_website_job(
                project_id, job_id,
                status="ready",
                status_message="Website generated successfully!",
                files=created_files,
                pages_created=pages_created,
                features_implemented=features_implemented,
                cdn_libraries_used=cdn_libraries,
                summary=summary,
                preview_url=f"/api/v1/projects/{project_id}/studio/websites/{job_id}/preview",
                download_url=f"/api/v1/projects/{project_id}/studio/websites/{job_id}/download",
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "site_name": site_name,
                "pages_created": pages_created,
                "files": created_files,
                "images": generated_images,
                "features": features_implemented,
                "cdn_libraries": cdn_libraries,
                "summary": summary,
                "preview_url": f"/api/v1/projects/{project_id}/studio/websites/{job_id}/preview",
                "download_url": f"/api/v1/projects/{project_id}/studio/websites/{job_id}/download",
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error finalizing website: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_website_job(
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
        Get source content for the website.

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
                return f"Source: {source.get('name', 'Unknown')}\\n(Content not yet processed)"

            with open(processed_path, "r", encoding="utf-8") as f:
                full_content = f.read()

            # If content is small enough, use it all
            if len(full_content) < 15000:  # ~3750 tokens
                return full_content

            # For large sources, sample chunks
            chunks_dir = os.path.join(sources_dir, "chunks", source_id)
            if not os.path.exists(chunks_dir):
                # No chunks, return truncated content
                return full_content[:15000] + "\\n\\n[Content truncated...]"

            # Get all chunks
            chunk_files = sorted([
                f for f in os.listdir(chunks_dir)
                if f.endswith(".txt") and f.startswith(source_id)
            ])

            if not chunk_files:
                return full_content[:15000] + "\\n\\n[Content truncated...]"

            # Sample up to 10 chunks evenly distributed
            max_chunks = 10
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

            return "\\n\\n".join(sampled_content)

        except Exception as e:
            print(f"[WebsiteAgent] Error getting source content: {e}")
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
            task=f"Generate website (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
website_agent_service = WebsiteAgentService()
