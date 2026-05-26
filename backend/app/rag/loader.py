import json
import asyncio
from pathlib import Path
from openai import AsyncOpenAI
from app.database import async_session
from app.models.rag import RagDocument
from app.config import settings

SEED_DOCS_PATH = Path("data/seed_docs")


async def load_seed_documents():
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    async with async_session() as db:
        for file_path in SEED_DOCS_PATH.glob("*.json"):
            with open(file_path) as f:
                docs = json.load(f)
            for doc in docs:
                embedding = await _embed(client, doc["content"])
                db.add(RagDocument(
                    title=doc["title"], content=doc["content"],
                    source=doc.get("source", "seed"),
                    source_url=doc.get("source_url"),
                    doc_type=doc.get("doc_type", "wiki"),
                    related_item_groups=doc.get("related_item_groups", []),
                    version=doc.get("version"),
                    language=doc.get("language", "zh"),
                    embedding=embedding,
                ))
        await db.commit()


async def _embed(client: AsyncOpenAI, text: str) -> list[float]:
    resp = await client.embeddings.create(model="text-embedding-3-small", input=text)
    return resp.data[0].embedding


def load_seed_documents_sync():
    asyncio.run(load_seed_documents())
