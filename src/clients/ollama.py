import httpx


async def chat_completion(base_url: str, payload: dict) -> httpx.Response:
    """
    Call Ollama's chat endpoint.
    """
    async with httpx.AsyncClient(base_url=base_url, timeout=60.0) as client:
        return await client.post(
            "/api/chat", json=payload, headers={"Content-Type": "application/json"}
        )
