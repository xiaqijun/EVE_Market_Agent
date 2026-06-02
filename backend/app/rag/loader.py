import json
import asyncio
import uuid
from pathlib import Path
from sqlalchemy import select, delete
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
                db.add(
                    RagDocument(
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
                    )
                )
                count += 1
        await db.commit()
        print(f"[RAG] Loaded {count} seed documents")


async def generate_embeddings():
    """Generate embeddings for documents that don't have them yet (local model)."""
    import asyncio

    model_name = settings.rag_embedding_model.replace("local:", "")
    from sentence_transformers import SentenceTransformer

    print(f"[RAG] Loading embedding model ({model_name})...")
    embedder = SentenceTransformer(model_name)

    async with async_session() as db:
        result = await db.execute(
            select(RagDocument).where(RagDocument.embedding.is_(None)).limit(500)
        )
        docs = result.scalars().all()
        for doc in docs:
            try:
                text = f"{doc.title}\n{doc.content[:2000]}"
                embedding = await asyncio.to_thread(embedder.encode, text)
                doc.embedding = embedding.tolist()
            except Exception as e:
                print(f"[RAG] Failed to embed doc {doc.id}: {e}")
        await db.commit()
        print(f"[RAG] Generated embeddings for {len(docs)} documents")


async def add_document(
    title: str,
    content: str,
    source: str = "manual",
    doc_type: str = "wiki",
    source_url: str | None = None,
    related_item_groups: list[int] | None = None,
    related_items: list[int] | None = None,
    version: str | None = None,
    language: str = "zh",
    auto_embed: bool = True,
) -> dict:
    """Add a new RAG document. Optionally generate embedding immediately."""
    async with async_session() as db:
        doc = RagDocument(
            title=title,
            content=content,
            source=source,
            source_url=source_url,
            doc_type=doc_type,
            related_item_groups=related_item_groups or [],
            related_items=related_items or [],
            version=version,
            language=language,
            embedding=None,
        )
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        doc_dict = {
            "id": str(doc.id),
            "title": doc.title,
            "content": doc.content,
            "source": doc.source,
            "doc_type": doc.doc_type,
        }

        if auto_embed:
            try:
                await _embed_single(doc)
            except Exception as e:
                print(f"[RAG] Failed to embed new doc {doc.id}: {e}")

        return doc_dict


async def update_document(doc_id: str, **kwargs) -> bool:
    """Update a RAG document by ID. Returns True if found and updated."""
    async with async_session() as db:
        result = await db.execute(select(RagDocument).where(RagDocument.id == uuid.UUID(doc_id)))
        doc = result.scalar_one_or_none()
        if not doc:
            return False
        for key, value in kwargs.items():
            if hasattr(doc, key) and key not in ("id", "created_at"):
                setattr(doc, key, value)
        # Reset embedding if content changed so it gets re-embedded
        if "content" in kwargs or "title" in kwargs:
            doc.embedding = None
        await db.commit()
        return True


async def delete_document(doc_id: str) -> bool:
    """Delete a RAG document by ID. Returns True if found and deleted."""
    async with async_session() as db:
        result = await db.execute(delete(RagDocument).where(RagDocument.id == uuid.UUID(doc_id)))
        await db.commit()
        return result.rowcount > 0


async def list_documents(
    doc_type: str | None = None,
    source: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict:
    """List RAG documents with optional filtering and pagination."""
    async with async_session() as db:
        query = select(RagDocument)
        if doc_type:
            query = query.where(RagDocument.doc_type == doc_type)
        if source:
            query = query.where(RagDocument.source == source)
        # Count
        from sqlalchemy import func

        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar()
        # Fetch page
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        docs = [
            {
                "id": str(doc.id),
                "title": doc.title,
                "source": doc.source,
                "doc_type": doc.doc_type,
                "version": doc.version,
                "language": doc.language,
                "has_embedding": doc.embedding is not None,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in result.scalars().all()
        ]
        return {"total": total, "offset": offset, "limit": limit, "documents": docs}


async def _embed_single(doc: RagDocument):
    """Generate embedding for a single document."""
    import asyncio

    model_name = settings.rag_embedding_model.replace("local:", "")
    from sentence_transformers import SentenceTransformer

    embedder = SentenceTransformer(model_name)
    text = f"{doc.title}\n{doc.content[:2000]}"
    embedding = await asyncio.to_thread(embedder.encode, text)

    async with async_session() as db:
        result = await db.execute(select(RagDocument).where(RagDocument.id == doc.id))
        db_doc = result.scalar_one_or_none()
        if db_doc:
            db_doc.embedding = embedding.tolist()
            await db.commit()


def load_seed_documents_sync():
    asyncio.run(load_seed_documents())


def generate_embeddings_sync():
    asyncio.run(generate_embeddings())
