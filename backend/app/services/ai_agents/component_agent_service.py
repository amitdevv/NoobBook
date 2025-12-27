"""
Component Agent Service - AI agent for generating UI component variations.

Educational Note: Simple agentic loop pattern with 2 tools:
1. Agent plans 2-4 component variations (plan_components)
2. Agent writes complete HTML/CSS/JS code for all variations (write_component_code - termination)

This demonstrates a streamlined agent workflow focused on creative design generation.
"""

import os
import uuid
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

from app.services.integrations.claude import claude_service
from app.config import prompt_loader, tool_loader
from app.utils import claude_parsing_utils
from app.utils.path_utils import get_studio_dir, get_sources_dir
from app.services.data_services import message_service
from app.services.studio_services import studio_index_service


class ComponentAgentService:
    """
    Component generation agent with simple 2-step workflow.

    Educational Note: This agent demonstrates a focused creative workflow:
    - No file operations (agent writes complete code in tool call)
    - No image generation (components use CSS/SVG for visuals)
    - Clean plan → generate pattern
    """

    AGENT_NAME = "component_agent"
    MAX_ITERATIONS = 10  # Simpler workflow, fewer iterations needed

    def __init__(self):
        """Initialize agent with lazy-loaded config and tools."""
        self._prompt_config = None
        self._tools = None

    def _load_config(self) -> Dict[str, Any]:
        """Lazy load prompt configuration."""
        if self._prompt_config is None:
            self._prompt_config = prompt_loader.get_prompt_config("component_agent")
        return self._prompt_config

    def _load_tools(self) -> List[Dict[str, Any]]:
        """Load both agent tools."""
        if self._tools is None:
            self._tools = tool_loader.load_tools_for_agent(self.AGENT_NAME)
        return self._tools

    # =========================================================================
    # Main Agent Execution
    # =========================================================================

    def generate_components(
        self,
        project_id: str,
        source_id: str,
        job_id: str,
        direction: str = ""
    ) -> Dict[str, Any]:
        """
        Run the agent to generate component variations.

        Educational Note: The agent workflow:
        1. Get source content and direction
        2. Agent plans 2-4 component variations
        3. Agent writes complete HTML/CSS/JS for each variation
        4. We save the components and update job status
        """
        config = self._load_config()
        tools = self._load_tools()

        execution_id = str(uuid.uuid4())
        started_at = datetime.now().isoformat()

        # Update job status
        studio_index_service.update_component_job(
            project_id, job_id,
            status="processing",
            status_message="Starting component generation..."
        )

        # Get source content
        source_content = self._get_source_content(project_id, source_id)

        # Build initial user message
        user_message = f"""Create 2-4 professional UI component variations based on the following source content.

=== SOURCE CONTENT ===
{source_content}
=== END SOURCE CONTENT ===

Direction from user: {direction if direction else 'No specific direction provided - use your best judgment based on the content.'}

Please create complete, production-ready components following the workflow:
1. Plan 2-4 distinct component variations (different styles, not just colors)
2. Write complete HTML/CSS/JS code for each variation (self-contained HTML documents)
3. Make each variation unique and professional"""

        messages = [{"role": "user", "content": user_message}]

        total_input_tokens = 0
        total_output_tokens = 0

        print(f"[ComponentAgent] Starting (job_id: {job_id[:8]})")

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

                    # Tool 1: Plan components
                    if tool_name == "plan_components":
                        result = self._handle_plan_components(project_id, job_id, tool_input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result
                        })

                    # Tool 2: Write component code (TERMINATION)
                    elif tool_name == "write_component_code":
                        final_result = self._handle_write_component_code(
                            project_id, job_id, source_id, tool_input,
                            iteration, total_input_tokens, total_output_tokens
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

        studio_index_service.update_component_job(
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

    def _handle_plan_components(
        self,
        project_id: str,
        job_id: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Handle plan_components tool call."""
        component_category = tool_input.get("component_category", "other")
        component_description = tool_input.get("component_description", "")
        variations = tool_input.get("variations", [])

        print(f"      Planning: {component_category} ({len(variations)} variations)")

        # Update job with plan
        studio_index_service.update_component_job(
            project_id, job_id,
            component_category=component_category,
            component_description=component_description,
            variations_planned=variations,
            technical_notes=tool_input.get("technical_notes"),
            status_message=f"Planned {len(variations)} variations, generating code..."
        )

        variation_names = [v.get("variation_name", "Unnamed") for v in variations]
        return f"Component plan saved successfully. Category: {component_category}, Variations: {', '.join(variation_names)}"

    def _handle_write_component_code(
        self,
        project_id: str,
        job_id: str,
        source_id: str,
        tool_input: Dict[str, Any],
        iterations: int,
        input_tokens: int,
        output_tokens: int
    ) -> Dict[str, Any]:
        """Handle write_component_code tool call (termination)."""
        components = tool_input.get("components", [])
        usage_notes = tool_input.get("usage_notes", "")

        print(f"      Writing code for {len(components)} components")

        try:
            # Prepare output directory
            studio_dir = get_studio_dir(project_id)
            component_dir = Path(studio_dir) / "components" / job_id
            component_dir.mkdir(parents=True, exist_ok=True)

            # Save each component as HTML file
            saved_components = []
            for idx, component in enumerate(components):
                variation_name = component.get("variation_name", f"Variation {idx + 1}")
                html_code = component.get("html_code", "")
                description = component.get("description", "")

                # Create safe filename
                safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in variation_name)
                safe_name = safe_name.replace(' ', '_').lower()
                filename = f"{safe_name}.html"

                # Save HTML file
                file_path = component_dir / filename
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(html_code)

                print(f"      Saved: {filename}")

                # Track component
                saved_components.append({
                    "variation_name": variation_name,
                    "filename": filename,
                    "description": description,
                    "preview_url": f"/api/v1/projects/{project_id}/studio/components/{job_id}/preview/{filename}",
                    "char_count": len(html_code)
                })

            # Get job info for component category
            job = studio_index_service.get_component_job(project_id, job_id)
            component_category = job.get("component_category", "component")
            component_description = job.get("component_description", "")

            # Update job to ready
            studio_index_service.update_component_job(
                project_id, job_id,
                status="ready",
                status_message="Components generated successfully!",
                components=saved_components,
                usage_notes=usage_notes,
                iterations=iterations,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                completed_at=datetime.now().isoformat()
            )

            return {
                "success": True,
                "job_id": job_id,
                "component_category": component_category,
                "component_description": component_description,
                "components": saved_components,
                "usage_notes": usage_notes,
                "iterations": iterations,
                "usage": {"input_tokens": input_tokens, "output_tokens": output_tokens}
            }

        except Exception as e:
            error_msg = f"Error writing component code: {str(e)}"
            print(f"      {error_msg}")

            studio_index_service.update_component_job(
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
        Get source content for component generation.

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
            if len(full_content) < 15000:  # ~3750 tokens
                return full_content

            # For large sources, sample chunks
            chunks_dir = os.path.join(sources_dir, "chunks", source_id)
            if not os.path.exists(chunks_dir):
                # No chunks, return truncated content
                return full_content[:15000] + "\n\n[Content truncated...]"

            # Get all chunks
            chunk_files = sorted([
                f for f in os.listdir(chunks_dir)
                if f.endswith(".txt") and f.startswith(source_id)
            ])

            if not chunk_files:
                return full_content[:15000] + "\n\n[Content truncated...]"

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
            print(f"[ComponentAgent] Error getting source content: {e}")
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
            task=f"Generate components (job: {job_id[:8]})",
            messages=messages,
            result=result,
            started_at=started_at,
            metadata={"source_id": source_id, "job_id": job_id}
        )


# Singleton instance
component_agent_service = ComponentAgentService()
