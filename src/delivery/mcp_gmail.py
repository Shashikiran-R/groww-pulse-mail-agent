"""
Gmail Drafter & Sender via Google Workspace MCP Server.

Interacts with aiagentserver.onrender.com tools:
- gmail_preview_email: Validates email fields and generates a human approval request.
- gmail_send_email: Dispatches an already approved email using action_id and idempotency_key.

Handles doc link injection, retries, exponential backoff, and human-in-the-loop approval URLs.
"""

from __future__ import annotations

import uuid
import asyncio
import logging
from pathlib import Path
from typing import Optional, Any, Dict, List, Union

from src.delivery.mcp_client import (
    DeliveryError,
    DeliveryApprovalResult,
    parse_tool_content,
    create_mcp_client,
    load_and_validate_mcp_config,
)

logger = logging.getLogger(__name__)


class MCPGmailDrafter:
    """
    Creates email previews & drafts for weekly pulse reports via Google Workspace MCP server tools.
    """

    def __init__(self, mcp_config_path: str = "mcp_config.json", client: Any | None = None):
        self.mcp_config_path = mcp_config_path
        self._custom_client = client

    async def _get_client(self):
        if self._custom_client:
            return self._custom_client
        return create_mcp_client(self.mcp_config_path, "google-workspace")

    def _inject_doc_banner(self, body_html: str, doc_url: str) -> str:
        """Inject an attractive accent card linking to the Google Doc."""
        doc_banner = (
            f'<div style="margin: 16px 0 24px 0; padding: 14px 18px; background-color: #f0fdf4; '
            f'border: 1px solid #bbf7d0; border-radius: 8px; font-family: -apple-system, BlinkMacSystemFont, '
            f'\'Segoe UI\', Roboto, sans-serif;">'
            f'<span style="font-size: 16px;">📄</span> <strong>Live Google Doc:</strong> '
            f'<a href="{doc_url}" style="color: #00d09c; text-decoration: none; font-weight: 600; margin-left: 6px;">'
            f'Open Groww Weekly Pulse Report &rarr;</a>'
            f'</div>'
        )
        if "</h1>" in body_html:
            parts = body_html.split("</h1>", 1)
            return parts[0] + "</h1>" + doc_banner + parts[1]
        elif "<body" in body_html:
            parts = body_html.split(">", 1)
            return parts[0] + ">" + doc_banner + parts[1]
        return doc_banner + body_html

    async def preview_email(
        self,
        subject: str,
        body_html: str,
        to: Union[str, list[str]],
        doc_url: Optional[str] = None,
        text_body: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        max_retries: int = 3,
    ) -> DeliveryApprovalResult:
        """
        Calls gmail_preview_email via MCP to validate email and create an approval request.

        Args:
            subject: Email subject line.
            body_html: HTML content of the pulse report.
            to: Recipient email address or list of addresses.
            doc_url: Optional Google Doc URL to link in the email.
            text_body: Optional fallback plain text.
            cc: Optional CC email addresses.
            bcc: Optional BCC email addresses.
            max_retries: Number of retry attempts.

        Returns:
            DeliveryApprovalResult with status, action_id, approval_url, preview, expires_at.
        """
        to_list = [to] if isinstance(to, str) else list(to)
        final_html = self._inject_doc_banner(body_html, doc_url) if doc_url else body_html
        plain_text = text_body or "Please view the HTML version or Google Doc for the full Groww Weekly Pulse report."

        delay = 2.0
        last_error = None

        for attempt in range(1, max_retries + 1):
            client = None
            try:
                client = await self._get_client()
                await client.start()

                # Call tool gmail_preview_email
                tool_args: dict[str, Any] = {
                    "to": to_list,
                    "subject": subject,
                    "html_body": final_html,
                    "text_body": plain_text,
                }
                if cc:
                    tool_args["cc"] = cc
                if bcc:
                    tool_args["bcc"] = bcc

                logger.info(f"Calling gmail_preview_email (attempt {attempt}/{max_retries})...")
                res = await client.call_tool("gmail_preview_email", tool_args)
                parsed = parse_tool_content(res)

                if parsed.get("status") == "error":
                    raise DeliveryError(f"gmail_preview_email error: {parsed.get('message', parsed)}")

                action_id = parsed.get("action_id")
                approval_url = parsed.get("approval_url")
                expires_at = parsed.get("expires_at")

                logger.info(f"Gmail email preview created. Approval URL: {approval_url}")
                return DeliveryApprovalResult(
                    status=parsed.get("status", "pending_approval"),
                    action_id=action_id,
                    approval_url=approval_url,
                    target_url=None,
                    preview=parsed.get("preview"),
                    expires_at=expires_at,
                )

            except Exception as e:
                last_error = e
                logger.warning(f"Gmail MCP preview_email failed (attempt {attempt}/{max_retries}): {e}")
                if attempt < max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2
            finally:
                if client and not self._custom_client:
                    await client.stop()

        raise DeliveryError(f"Failed to preview Gmail email after {max_retries} attempts: {last_error}")

    async def send_email(
        self,
        action_id: str,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        """
        Calls gmail_send_email for an already approved action.
        """
        key = idempotency_key or str(uuid.uuid4())
        client = await self._get_client()
        try:
            await client.start()
            res = await client.call_tool("gmail_send_email", {
                "action_id": action_id,
                "idempotency_key": key,
            })
            return parse_tool_content(res)
        finally:
            if not self._custom_client:
                await client.stop()

    async def draft(
        self,
        subject: str,
        body_html: str,
        to: str,
        doc_url: Optional[str] = None,
        max_retries: int = 3,
    ) -> str:
        """
        Create Gmail preview/draft via MCP tool call (backwards-compatible entrypoint).

        Returns:
            Approval URL or draft action_id string.
        """
        result = await self.preview_email(
            subject=subject,
            body_html=body_html,
            to=to,
            doc_url=doc_url,
            max_retries=max_retries,
        )
        return result.action_id or result.approval_url or f"draft_{int(asyncio.get_event_loop().time())}"

