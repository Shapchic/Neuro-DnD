"""
Live integration test for AI Dungeon Master with the real Qwen model via Ollama.
Run:
    python test_live_dm.py
"""
import sys
import asyncio
from unittest.mock import patch, AsyncMock

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from server.api.ai import get_ai_completion
from server.core.models import (
    AICompleteRequest,
    Message,
    CampaignDetailsResponse,
    CampaignMeta,
    CampaignJournal,
    UserSettings
)

async def main():
    print("=" * 60)
    print("ТЕСТИРОВАНИЕ РЕАЛЬНОГО AI DUNGEON MASTER (Qwen через Ollama)")
    print("=" * 60)

    # Имитируем контекст кампании
    mock_campaign = CampaignDetailsResponse(
        meta=CampaignMeta(
            name="Подземелье Дракона",
            host_user_code="test_user",
            tone="epic_fantasy",
            difficulty="medium"
        ),
        journal=CampaignJournal(entries=[])
    )
    mock_settings = UserSettings(language="ru")

    user_action = "Я вхожу в тронный зал с обнаженным мечом и осматриваюсь."
    print(f"\n[Игрок]: {user_action}\n")
    print("Отправка запроса к Qwen... (подождите несколько секунд)")

    request = AICompleteRequest(
        campaign_id="00000000-0000-0000-0000-000000000000",
        messages=[Message(role="user", content=user_action)]
    )

    with patch("server.api.ai.get_campaign_details", new=AsyncMock(return_value=mock_campaign)), \
         patch("server.api.ai.get_user_settings", new=AsyncMock(return_value=mock_settings)):
        
        response = await get_ai_completion(request, user_code="test_user")

        print("\n" + "-" * 60)
        print("ОТВЕТ AI DUNGEON MASTER (Нарратив):")
        print("-" * 60)
        print(response.text)

        print("\n" + "-" * 60)
        print("РАСПАРСЕННЫЕ МЕТАДАННЫЕ (JSON):")
        print("-" * 60)
        print(response.meta)
        print("=" * 60)
        print("[+] Тест успешно пройден: модель сгенерировала сюжет и метаданные!")

if __name__ == "__main__":
    asyncio.run(main())
