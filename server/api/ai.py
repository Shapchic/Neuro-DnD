import re
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException

from server.core import config, storage
from server.core.models import AICompleteRequest, AICompleteResponse, Message
from server.api.auth import get_current_user_code, get_current_user

router = APIRouter(prefix="/ai", tags=["AI"])

def parse_ai_response(response_text: str) -> AICompleteResponse:
    """
    Parses the raw text from the AI, separating the narrative
    from the structured JSON metadata block.
    """
    json_block_match = re.search(r"```json\r?\n({.*?})\r?\n```", response_text, re.DOTALL)

    text_content = response_text
    meta_data = None

    if json_block_match:
        json_str = json_block_match.group(1)
        text_content = response_text.replace(json_block_match.group(0), "").strip()
        try:
            meta_data = json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Warning: Failed to parse JSON metadata from AI response: {json_str}")
            meta_data = {"error": "failed_to_parse_json"}

    return AICompleteResponse(text=text_content, meta=meta_data)


@router.post("/complete", response_model=AICompleteResponse)
async def get_ai_completion(
    request: AICompleteRequest,
    user_code: str = Depends(get_current_user_code)
):
    """
    Generates a response from the AI Dungeon Master using local Qwen inference.
    """
    # 1. Gather context
    campaign_details = await get_campaign_details(request.campaign_id, user_code)
    user_settings = await get_user_settings(user_code)

    try:
        with open(config.SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="System prompt file not found.")

    # 2. Construct the prompt
    full_prompt_context = f"""{system_prompt}

---
## Game Context
- Campaign Name: {campaign_details.meta.name}
- Tone: {campaign_details.meta.tone}
- Difficulty: {campaign_details.meta.difficulty}
- Language: {user_settings.language}
---
"""

    final_prompt_list = [full_prompt_context]
    for msg in request.messages:
        final_prompt_list.append(f"**{msg.role.capitalize()}:** {msg.content}")

    prompt_text = "\n".join(final_prompt_list)

    # 3. Call local Qwen (Ollama API)
    payload = {
        "model": config.QWEN_TEXT_MODEL,
        "prompt": prompt_text,
        "stream": False,
    }

    try:
        async with httpx.AsyncClient(timeout=config.QWEN_TIMEOUT) as client:
            response = await client.post(config.QWEN_API_URL, json=payload)
            response.raise_for_status()
            data = response.json()
            response_text = data.get("response", "")
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=504,
            detail=f"Timeout waiting for AI inference service ({config.QWEN_TIMEOUT}s): {str(exc)}"
        )
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"AI service returned HTTP error {exc.response.status_code}: {exc.response.text}"
        )
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to AI service: {str(exc)}"
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error calling AI service: {str(exc)}"
        )

    # 4. Parse and return response
    return parse_ai_response(response_text)

# Need to import these from the other routers to avoid circular dependencies
from server.api.campaigns import get_campaign_details
from server.api.users import get_user_settings
