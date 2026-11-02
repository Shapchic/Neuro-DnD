import sys
import os
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import httpx
from fastapi import HTTPException

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.core import config
from server.api.ai import parse_ai_response, get_ai_completion
from server.core.models import AICompleteRequest, Message, CampaignMeta, CampaignJournal, CampaignDetailsResponse, UserSettings

def test_parse_ai_response_with_valid_metadata():
    print("Testing parse_ai_response with valid metadata...")
    raw = (
        "You step into the dark dungeon.\n\n"
        "1. Light a torch.\n"
        "2. Step forward cautiously.\n"
        "```json\n"
        '{"mood": "tense", "location": "dungeon_entrance"}\n'
        "```"
    )
    result = parse_ai_response(raw)
    assert "You step into the dark dungeon." in result.text
    assert "```json" not in result.text
    assert result.meta == {"mood": "tense", "location": "dungeon_entrance"}
    print("OK")

def test_parse_ai_response_without_metadata():
    print("Testing parse_ai_response without metadata...")
    raw = "The dragon roars and vanishes into the sky."
    result = parse_ai_response(raw)
    assert result.text == raw
    assert result.meta is None
    print("OK")

def test_parse_ai_response_with_malformed_metadata():
    print("Testing parse_ai_response with malformed metadata...")
    raw = (
        "A chest sits in the corner.\n"
        "```json\n"
        '{invalid_json: true}\n'
        "```"
    )
    result = parse_ai_response(raw)
    assert "A chest sits in the corner." in result.text
    assert result.meta == {"error": "failed_to_parse_json"}
    print("OK")

def test_qwen_endpoint_success():
    print("Testing get_ai_completion with successful Qwen inference...")

    mock_campaign = CampaignDetailsResponse(
        meta=CampaignMeta(name="Test Campaign", host_user_code="user-123"),
        journal=CampaignJournal(entries=[])
    )
    mock_user_settings = UserSettings(language="ru")

    request = AICompleteRequest(
        campaign_id="11111111-1111-1111-1111-111111111111",
        messages=[Message(role="user", content="Я осматриваю комнату.")]
    )

    qwen_response_text = (
        "Вы видите древний каменный алтарь.\n\n"
        "1. Подойти к алтарю.\n"
        "2. Осмотреть стены.\n"
        "```json\n"
        '{"mood": "mysterious", "location": "altar_room"}\n'
        "```"
    )

    async def run():
        captured_request = {}

        class DummyResponse:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"response": qwen_response_text}

        class DummyAsyncClient:
            def __init__(self, timeout=None):
                self.timeout = timeout
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            async def post(self, url, json=None):
                captured_request["url"] = url
                captured_request["json"] = json
                return DummyResponse()

        with patch("server.api.ai.get_campaign_details", new=AsyncMock(return_value=mock_campaign)), \
             patch("server.api.ai.get_user_settings", new=AsyncMock(return_value=mock_user_settings)), \
             patch("httpx.AsyncClient", new=DummyAsyncClient):
            
            resp = await get_ai_completion(request, user_code="user-123")
            assert "Вы видите древний каменный алтарь." in resp.text
            assert resp.meta == {"mood": "mysterious", "location": "altar_room"}
            assert captured_request["url"] == config.QWEN_API_URL
            assert captured_request["json"]["model"] == config.QWEN_TEXT_MODEL
            assert captured_request["json"]["stream"] is False
            assert "Я осматриваю комнату." in captured_request["json"]["prompt"]

    asyncio.run(run())
    print("OK")

def test_qwen_endpoint_timeout():
    print("Testing get_ai_completion handling timeout (504)...")

    mock_campaign = CampaignDetailsResponse(
        meta=CampaignMeta(name="Test Campaign", host_user_code="user-123"),
        journal=CampaignJournal(entries=[])
    )
    mock_user_settings = UserSettings(language="ru")
    request = AICompleteRequest(
        campaign_id="11111111-1111-1111-1111-111111111111",
        messages=[Message(role="user", content="Test action")]
    )

    async def run():
        class DummyAsyncClientTimeout:
            def __init__(self, timeout=None):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            async def post(self, url, json=None):
                raise httpx.ReadTimeout("Inference timed out")

        with patch("server.api.ai.get_campaign_details", new=AsyncMock(return_value=mock_campaign)), \
             patch("server.api.ai.get_user_settings", new=AsyncMock(return_value=mock_user_settings)), \
             patch("httpx.AsyncClient", new=DummyAsyncClientTimeout):
            
            try:
                await get_ai_completion(request, user_code="user-123")
                assert False, "Should have raised HTTPException 504"
            except HTTPException as e:
                assert e.status_code == 504
                assert "timed out" in e.detail.lower()

    asyncio.run(run())
    print("OK")

def test_qwen_endpoint_connection_error():
    print("Testing get_ai_completion handling connection failure (503)...")

    mock_campaign = CampaignDetailsResponse(
        meta=CampaignMeta(name="Test Campaign", host_user_code="user-123"),
        journal=CampaignJournal(entries=[])
    )
    mock_user_settings = UserSettings(language="ru")
    request = AICompleteRequest(
        campaign_id="11111111-1111-1111-1111-111111111111",
        messages=[Message(role="user", content="Test action")]
    )

    async def run():
        class DummyAsyncClientConnectError:
            def __init__(self, timeout=None):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass
            async def post(self, url, json=None):
                raise httpx.ConnectError("Connection refused")

        with patch("server.api.ai.get_campaign_details", new=AsyncMock(return_value=mock_campaign)), \
             patch("server.api.ai.get_user_settings", new=AsyncMock(return_value=mock_user_settings)), \
             patch("httpx.AsyncClient", new=DummyAsyncClientConnectError):
            
            try:
                await get_ai_completion(request, user_code="user-123")
                assert False, "Should have raised HTTPException 503"
            except HTTPException as e:
                assert e.status_code == 503
                assert "connect" in e.detail.lower()

    asyncio.run(run())
    print("OK")

if __name__ == "__main__":
    print("--- Running Qwen AI Integration Tests ---")
    test_parse_ai_response_with_valid_metadata()
    test_parse_ai_response_without_metadata()
    test_parse_ai_response_with_malformed_metadata()
    test_qwen_endpoint_success()
    test_qwen_endpoint_timeout()
    test_qwen_endpoint_connection_error()
    print("--- All AI tests passed successfully! ---")
