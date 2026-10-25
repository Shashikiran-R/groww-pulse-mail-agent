"""
Google Docs Publisher via Google Workspace MCP Server.

Interacts with aiagentserver.onrender.com tools:
- docs_preview_append: Validates append target/content & creates approval request.
- docs_append_text: Appends text once approved.
- docs_get_document_info: Fetches metadata & tab information.

Handles retries, exponential backoff, and human-in-the-loop approval URLs.
"""

from __future__ import annotations

import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional, Any, Dict

from src.config import config
from src.delivery.mcp_client import (
    DeliveryError,
    DeliveryApprovalResult,
    parse_tool_content,
    create_mcp_client,
    load_and_validate_mcp_config,
)

logger = logging.getLogger(__name__)


class MCPDocsPublisher:
    """
    Publishes weekly pulse reports to Google Docs via Google Workspace MCP server tools.
    """

    def __init__(self, mcp_config_path: str = "mcp_config.json", client: Any | None = None):
        self.mcp_config_path = mcp_config_path
        self._custom_client = client
        self.doc_url_or_id = (
            getattr(config, "GROWW_PULSE_DOC_URL", "")
            or getattr(config, "GROWW_PULSE_DOC_ID", "")
            or "https://docs.google.com/document/d/groww-weekly-pulse/edit"
        )

    async def _get_client(self):
        if self._custom_client:
            return self._custom_client
        return create_mcp_client(self.mcp_config_path, "google-workspace")

    async def get_info(self, doc_url_or_id: Optional[str] = None) -> dict[str, Any]:
        """
        Calls docs_get_document_info via MCP to validate access and retrieve doc tabs & revision ID.
        """
        target = doc_url_or_id or self.doc_url_or_id
        client = await self._get_client()
        try:
            await client.start()
            res = await client.call_tool("docs_get_document_info", {"document_url_or_id": target})
            parsed = parse_tool_content(res)
            if parsed.get("status") == "error":
                raise DeliveryError(f"docs_get_document_info error: {parsed.get('message', parsed)}")
            return parsed
        finally:
            if not self._custom_client:
                await client.stop()

    async def preview_append(
        self,
        content_md: str,
        doc_url_or_id: Optional[str] = None,
        tab_id: Optional[str] = None,
        separator: str = "blank_line",
        max_retries: int = 3,
    ) -> DeliveryApprovalResult:
        """
        Calls docs_preview_append via MCP to validate content and generate a human approval request.

        Args:
            content_md: Markdown text of the weekly pulse report.
            doc_url_or_id: Target Google Doc URL or ID. Defaults to config.GROWW_PULSE_DOC_URL.
            tab_id: Optional specific tab ID within the document.
            separator: Separation before append ('blank_line', 'newline', or 'none').
            max_retries: Number of retry attempts.

        Returns:
            DeliveryApprovalResult with status, action_id, approval_url, target_url, expires_at.
        """
        target = doc_url_or_id or self.doc_url_or_id
        delay = 2.0
        last_error = None

        for attempt in range(1, max_retries + 1):
            client = None
            try:
                client = await self._get_client()
                await client.start()

                # Call tool docs_preview_append
                tool_args: dict[str, Any] = {
                    "document_url_or_id": target,
                    "text": content_md,
                    "separator": separator,
                }
                if tab_id:
                    tool_args["tab_id"] = tab_id

                logger.info(f"Calling docs_preview_append (attempt {attempt}/{max_retries})...")
                res = await client.call_tool("docs_preview_append", tool_args)
                parsed = parse_tool_content(res)

                # Check if tool returned error
                if parsed.get("status") == "error":
                    raise DeliveryError(f"docs_preview_append error: {parsed.get('message', parsed)}")

                action_id = parsed.get("action_id")
                approval_url = parsed.get("approval_url")
                expires_at = parsed.get("expires_at")
                target_url = (
                    parsed.get("preview", {}).get("document_url")
                    or parsed.get("document_url")
                    or target
                )

                logger.info(f"Docs append preview created. Approval URL: {approval_url}")
                return DeliveryApprovalResult(
                    status=parsed.get("status", "pending_approval"),
                    action_id=action_id,
                    approval_url=approval_url,
                    target_url=target_url,
                    preview=parsed.get("preview"),
                    expires_at=expires_at,
                )

            except Exception as e:
                last_error = e
                logger.warning(f"Google Docs MCP preview_append failed (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2
            finally:
                if client and not self._custom_client:
                    await client.stop()

        raise DeliveryError(f"Failed to preview Google Docs append after {max_retries} attempts: {last_error}")

    async def append_text(
        self,
        action_id: str,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Executes docs_append_text for an already approved action.
        """
        key = idempotency_key or str(uuid.uuid4())
        client = await self._get_client()
        try:
            await client.start()
            res = await client.call_tool("docs_append_text", {
                "action_id": action_id,
                "idempotency_key": key,
            })
            return parse_tool_content(res)
        finally:
            if not self._custom_client:
                await client.stop()

    async def publish(self, title: str, content_md: str, max_retries: int = 3) -> str:
        """
        Create/preview Google Doc via MCP tool call (backwards-compatible entrypoint).

        Returns:
            Document URL or approval URL string.
        """
        result = await self.preview_append(content_md=content_md, max_retries=max_retries)
        return result.target_url or result.approval_url or "https://docs.google.com/document/d/pulse/edit"

