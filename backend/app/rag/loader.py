import json
import asyncio
from pathlib import Path
from sqlalchemy import select
from app.database import async_session
from app.models.rag import RagDocument
from app.config import settings

SEED_DOCS_PATH = Path("/app/data/seed_docs")


async def load_seed_documents():
    """Load seed documents without embeddings (keyword search only)."""
    async with async_session() as db:
        count = 0
        for file_path in SEED_DOCS_PATH.glob("*.json"):
            with open(file_path) as f:
                docs = json.load(f)
            for doc in docs:
                existing = await db.execute(
                    select(RagDocument).where(
                        RagDocument.title == doc["title"],
                        RagDocument.source == doc.get("source", "seed"),
                    )
                )
                if existing.scalar_one_or_none():
                    continue
                db.add(RagDocument(
                    title=doc["title"],
                    content=doc["content"],
                    source=doc.get("source", "seed"),
                    source_url=doc.get("source_url"),
                    doc_type=doc.get("doc_type", "wiki"),
                    related_item_groups=doc.get("related_item_groups", []),
                    related_items=doc.get("related_items", []),
                    version=doc.get("version"),
                    language=doc.get("language", "zh"),
                    embedding=None,
                ))
                count += 1
        await db.commit()
        print(f"[RAG] Loaded {count} seed documents")


async def generate_embeddings():
    """Generate embeddings for documents that don't have them yet."""
    if not settings.openai_api_key:
        print("[RAG] No OpenAI API key configured, skipping embedding generation")
        return

    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    async with async_session() as db:
        result = await db.execute(
            select(RagDocument).where(RagDocument.embedding.is_(None)).limit(500)
        )
        docs = result.scalars().all()
        for doc in docs:
            try:
                resp = await client.embeddings.create(
                    model="text-embedding-3-small",
                    input=f"{doc.title}\n{doc.content[:2000]}",
                )
                doc.embedding = resp.data[0].embedding
            except Exception as e:
                print(f"[RAG] Failed to embed doc {doc.id}: {e}")
        await db.commit()
        print(f"[RAG] Generated embeddings for {len(docs)} documents")


def load_seed_documents_sync():
    asyncio.run(load_seed_documents())


def generate_embeddings_sync():
    asyncio.run(generate_embeddings())
