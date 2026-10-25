"""
Tests for MCP Delivery Layer — Google Workspace MCP Server (aiagentserver) integration.
"""

import json
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.delivery.mcp_client import (
    DeliveryError,
    DeliveryApprovalResult,
    parse_tool_content,
    load_and_validate_mcp_config,
)
from src.delivery.mcp_docs import MCPDocsPublisher
from src.delivery.mcp_gmail import MCPGmailDrafter


# ── Config Validation ─────────────────────────────────────────────────────

class TestMCPConfigValidation:

    def test_load_valid_stdio_config(self, tmp_path):
        """Loads and validates a correct stdio configuration."""
        cfg_file = tmp_path / "mcp_config.json"
        cfg_file.write_text("""{
            "mcpServers": {
                "google-workspace-local": {
                    "command": "node",
                    "args": ["dist/index.js", "--transport", "stdio"],
                    "env": {"APP_ENV": "local"}
                }
            }
        }""")

        conf = load_and_validate_mcp_config(cfg_file, "google-workspace-local")
        assert conf["type"] == "stdio"
        assert conf["command"] == "node"
        assert conf["args"] == ["dist/index.js", "--transport", "stdio"]
        assert conf["env"] == {"APP_ENV": "local"}

    def test_load_valid_sse_config(self, tmp_path):
        """Loads and validates remote SSE configuration with header interpolation."""
        cfg_file = tmp_path / "mcp_config.json"
        cfg_file.write_text("""{
            "mcpServers": {
                "google-workspace": {
                    "serverUrl": "https://aiagentserver.onrender.com/sse",
                    "headers": {
                        "Authorization": "Bearer test-secret-token"
                    }
                }
            }
        }""")

        conf = load_and_validate_mcp_config(cfg_file, "google-workspace")
        assert conf["type"] == "sse"
        assert conf["serverUrl"] == "https://aiagentserver.onrender.com/sse"
        assert conf["headers"]["Authorization"] == "Bearer test-secret-token"

    def test_missing_config_file_raises_error(self, tmp_path):
        """Missing config file raises DeliveryError."""
        missing = tmp_path / "non_existent.json"
        with pytest.raises(DeliveryError, match="not found"):
            load_and_validate_mcp_config(missing, "google-workspace")

    def test_missing_server_entry_raises_error(self, tmp_path):
        """Missing server name raises DeliveryError."""
        cfg_file = tmp_path / "mcp_config.json"
        cfg_file.write_text('{"mcpServers": {"other-server": {}}}')
        with pytest.raises(DeliveryError, match="not defined"):
            load_and_validate_mcp_config(cfg_file, "custom-unknown-server")


# ── Response Parser ───────────────────────────────────────────────────────

class TestToolContentParser:

    def test_parse_json_text_content(self):
        """Extracts JSON dict from MCP content block."""
        mcp_res = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps({
                        "status": "pending_approval",
                        "action_id": "act-123",
                        "approval_url": "https://aiagentserver.onrender.com/approve/act-123"
                    })
                }
            ]
        }
        parsed = parse_tool_content(mcp_res)
        assert parsed["status"] == "pending_approval"
        assert parsed["action_id"] == "act-123"
        assert parsed["approval_url"] == "https://aiagentserver.onrender.com/approve/act-123"


# ── Google Docs Publisher ─────────────────────────────────────────────────

class TestMCPDocsPublisher:

    @pytest.mark.anyio
    async def test_preview_append_success(self, tmp_path):
        """MCPDocsPublisher calls docs_preview_append and returns approval URL and target URL."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "status": "pending_approval",
                    "action_id": "doc-action-456",
                    "approval_url": "https://aiagentserver.onrender.com/approve/doc-action-456",
                    "preview": {
                        "document_id": "1abc_doc_id",
                        "document_url": "https://docs.google.com/document/d/1abc_doc_id/edit",
                        "text": "# Pulse Markdown"
                    }
                })
            }]
        })

        publisher = MCPDocsPublisher(client=mock_client)
        result = await publisher.preview_append(
            content_md="# Pulse Markdown",
            doc_url_or_id="https://docs.google.com/document/d/1abc_doc_id/edit"
        )

        assert isinstance(result, DeliveryApprovalResult)
        assert result.status == "pending_approval"
        assert result.action_id == "doc-action-456"
        assert result.approval_url == "https://aiagentserver.onrender.com/approve/doc-action-456"
        assert result.target_url == "https://docs.google.com/document/d/1abc_doc_id/edit"

        from src.delivery.doc_formatter import format_for_google_doc
        mock_client.call_tool.assert_called_once_with(
            "docs_preview_append",
            {
                "document_url_or_id": "https://docs.google.com/document/d/1abc_doc_id/edit",
                "text": format_for_google_doc("# Pulse Markdown"),
                "separator": "blank_line"
            }
        )

    @pytest.mark.anyio
    async def test_append_text_execution(self):
        """MCPDocsPublisher executes docs_append_text using action_id and idempotency key."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "provider": "google_docs",
                    "document_id": "1abc_doc_id",
                    "characters_appended": 140
                })
            }]
        })

        publisher = MCPDocsPublisher(client=mock_client)
        res = await publisher.append_text(action_id="doc-action-456", idempotency_key="idemp-key-1")

        assert res["provider"] == "google_docs"
        assert res["characters_appended"] == 140
        mock_client.call_tool.assert_called_once_with(
            "docs_append_text",
            {"action_id": "doc-action-456", "idempotency_key": "idemp-key-1"}
        )

    @pytest.mark.anyio
    async def test_preview_append_retries_and_raises_error(self):
        """Repeated failures raise DeliveryError after max retries."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(side_effect=Exception("Connection refused"))

        publisher = MCPDocsPublisher(client=mock_client)
        with pytest.raises(DeliveryError, match="Failed to preview Google Docs append after 3 attempts"):
            await publisher.preview_append(content_md="# Content", max_retries=3)


# ── Gmail Drafter ─────────────────────────────────────────────────────────

class TestMCPGmailDrafter:

    @pytest.mark.anyio
    async def test_preview_email_with_doc_link(self):
        """MCPGmailDrafter injects doc URL banner and calls gmail_preview_email."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "status": "pending_approval",
                    "action_id": "gmail-action-789",
                    "approval_url": "https://aiagentserver.onrender.com/approve/gmail-action-789",
                    "preview": {
                        "to": ["stakeholder@groww.in"],
                        "subject": "Groww Pulse 2026-W40"
                    }
                })
            }]
        })

        drafter = MCPGmailDrafter(client=mock_client)
        result = await drafter.preview_email(
            subject="Groww Pulse 2026-W40",
            body_html="<h1>Groww Weekly Pulse</h1><p>Body</p>",
            to="stakeholder@groww.in",
            doc_url="https://docs.google.com/document/d/xyz/edit"
        )

        assert isinstance(result, DeliveryApprovalResult)
        assert result.status == "pending_approval"
        assert result.action_id == "gmail-action-789"
        assert result.approval_url == "https://aiagentserver.onrender.com/approve/gmail-action-789"

        mock_client.call_tool.assert_called_once()
        call_args = mock_client.call_tool.call_args[0][1]
        assert call_args["to"] == ["stakeholder@groww.in"]
        assert call_args["subject"] == "Groww Pulse 2026-W40"
        assert "https://docs.google.com/document/d/xyz/edit" in call_args["html_body"]

    @pytest.mark.anyio
    async def test_send_email_execution(self):
        """MCPGmailDrafter executes gmail_send_email using action_id and idempotency key."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "provider": "gmail",
                    "message_id": "msg-123456"
                })
            }]
        })

        drafter = MCPGmailDrafter(client=mock_client)
        res = await drafter.send_email(action_id="gmail-action-789", idempotency_key="idemp-msg-1")

        assert res["provider"] == "gmail"
        assert res["message_id"] == "msg-123456"
        mock_client.call_tool.assert_called_once_with(
            "gmail_send_email",
            {"action_id": "gmail-action-789", "idempotency_key": "idemp-msg-1"}
        )

    @pytest.mark.anyio
    async def test_preview_email_with_cc_bcc_and_expires(self):
        """MCPGmailDrafter sends cc, bcc and captures expires_at."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "status": "pending_approval",
                    "action_id": "gmail-cc-123",
                    "approval_url": "https://aiagentserver.onrender.com/approve/gmail-cc-123",
                    "expires_at": "2026-10-25T16:00:00Z",
                    "preview": {
                        "to": ["to@groww.in"],
                        "cc": ["cc@groww.in"],
                        "bcc": ["bcc@groww.in"],
                        "subject": "Pulse with CC"
                    }
                })
            }]
        })

        drafter = MCPGmailDrafter(client=mock_client)
        res = await drafter.preview_email(
            subject="Pulse with CC",
            body_html="<p>Test</p>",
            to="to@groww.in",
            cc=["cc@groww.in"],
            bcc=["bcc@groww.in"],
        )

        assert res.action_id == "gmail-cc-123"
        assert res.expires_at == "2026-10-25T16:00:00Z"
        call_args = mock_client.call_tool.call_args[0][1]
        assert call_args["cc"] == ["cc@groww.in"]
        assert call_args["bcc"] == ["bcc@groww.in"]


# ── Diagnostics & Connection Status ────────────────────────────────────────

class TestMCPConnectionDiagnostics:

    @pytest.mark.anyio
    async def test_google_connection_status(self):
        """MCP client calls google_connection_status and returns parsed dict."""
        from src.delivery.mcp_client import StdioMCPClient
        client = StdioMCPClient(command="node", args=["index.js"])
        client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "connected": True,
                    "google_account_email": "shashikiran@groww.in",
                    "gmail_send_enabled": True,
                    "docs_edit_enabled": True,
                    "missing_scopes": [],
                    "reauthorization_required": False
                })
            }]
        })

        status = await client.check_connection_status()
        assert status["connected"] is True
        assert status["google_account_email"] == "shashikiran@groww.in"
        assert status["gmail_send_enabled"] is True
        assert status["docs_edit_enabled"] is True
        assert status["reauthorization_required"] is False

    @pytest.mark.anyio
    async def test_docs_get_document_info(self):
        """MCPDocsPublisher calls docs_get_document_info and returns tab metadata."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "documentId": "1a2b3c4d",
                    "title": "Groww Pulse Document",
                    "revisionId": "rev-99",
                    "tabs": [{"tab_id": "tab-1", "title": "2026 Pulses"}]
                })
            }]
        })

        publisher = MCPDocsPublisher(client=mock_client)
        info = await publisher.get_info("https://docs.google.com/document/d/1a2b3c4d/edit")
        assert info["documentId"] == "1a2b3c4d"
        assert info["title"] == "Groww Pulse Document"
        assert len(info["tabs"]) == 1
        assert info["tabs"][0]["tab_id"] == "tab-1"

    @pytest.mark.anyio
    async def test_docs_preview_append_with_tab_id_and_expires(self):
        """MCPDocsPublisher supports tab_id and extracts expires_at."""
        mock_client = MagicMock()
        mock_client.start = AsyncMock()
        mock_client.stop = AsyncMock()
        mock_client.call_tool = AsyncMock(return_value={
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "status": "pending_approval",
                    "action_id": "tab-act-1",
                    "approval_url": "https://aiagentserver.onrender.com/approve/tab-act-1",
                    "expires_at": "2026-10-25T16:10:00Z",
                    "preview": {"tab_id": "tab-1", "text": "## Content"}
                })
            }]
        })

        publisher = MCPDocsPublisher(client=mock_client)
        res = await publisher.preview_append(
            content_md="## Content",
            tab_id="tab-1",
        )
        assert res.action_id == "tab-act-1"
        assert res.expires_at == "2026-10-25T16:10:00Z"
        call_args = mock_client.call_tool.call_args[0][1]
        assert call_args["tab_id"] == "tab-1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

