from sqlalchemy.orm import Session

from app.models.chunk import Chunk


class ChunkRepository:
    @staticmethod
    def get_by_id(db: Session, *, chunk_id: str) -> Chunk | None:
        return db.get(Chunk, chunk_id)

    @staticmethod
    def list_by_document(db: Session, *, document_id: str) -> list[Chunk]:
        return db.query(Chunk).filter(Chunk.doc_id == document_id).order_by(Chunk.chunk_index).all()

    @staticmethod
    def save_batch(db: Session, *, chunks: list[Chunk]) -> list[Chunk]:
        db.add_all(chunks)
        db.flush()
        return chunks

    @staticmethod
    def delete_by_document(db: Session, *, document_id: str) -> None:
        db.query(Chunk).filter(Chunk.doc_id == document_id).delete()
        db.flush()

    @staticmethod
    def delete(db: Session, *, chunk: Chunk) -> None:
        db.delete(chunk)
        db.flush()
