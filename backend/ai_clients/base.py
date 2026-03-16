from abc import ABC, abstractmethod
from typing import AsyncIterator


class AIClient(ABC):
    @abstractmethod
    async def generate(self, messages: list[dict]) -> str: ...

    @abstractmethod
    async def generate_stream(self, messages: list[dict]) -> AsyncIterator[str]: ...
