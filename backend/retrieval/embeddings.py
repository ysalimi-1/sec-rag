import time
import openai
from openai import OpenAI
from backend.config import OPENAI_API_KEY, EMBEDDING_MODEL

_client = OpenAI(api_key=OPENAI_API_KEY)


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        while True:
            try:
                resp = _client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
                all_embeddings.extend([d.embedding for d in resp.data])
                break
            except openai.RateLimitError:
                print("Rate limit hit, retrying in 3 seconds...")
                time.sleep(3)
    return all_embeddings
