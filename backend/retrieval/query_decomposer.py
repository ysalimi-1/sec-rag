import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY, DECOMPOSE_MODEL
from backend.chat.prompts import get_decompose_system

_client = OpenAI(api_key=OPENAI_API_KEY)



from pydantic import BaseModel, Field

class SearchPlan(BaseModel):
    queries: list[str] = Field(description="2 to 8 search queries")
    tickers: list[str] = Field(description="List of uppercase stock tickers explicitly mentioned or implied by the sector")

def decompose_and_expand(query: str) -> SearchPlan:
    resp = _client.beta.chat.completions.parse(
        model=DECOMPOSE_MODEL,
        messages=[
            {"role": "system", "content": get_decompose_system()},
            {"role": "user", "content": query},
        ],
        response_format=SearchPlan,
    )
    return resp.choices[0].message.parsed
