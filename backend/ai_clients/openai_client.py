from typing import AsyncIterator
from openai import AsyncOpenAI
from backend.ai_clients.base import AIClient
from backend.config import OPENAI_API_KEY, LLM_MODEL


class OpenAIClient(AIClient):
    def __init__(self, model: str = None):
        self.model = model or LLM_MODEL
        self.client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    async def generate(self, messages: list[dict]) -> str:
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )
        return resp.choices[0].message.content

    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content
