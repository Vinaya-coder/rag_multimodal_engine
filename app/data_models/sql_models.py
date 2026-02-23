from sqlalchemy import Column, Integer, String, DateTime, func, Float, UniqueConstraint
from pgvector.sqlalchemy import Vector
from app.drivers.database import Base
class MediaVault(Base):
    __tablename__ = "media_vault"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))
    file_url = Column(String(500))
    description = Column(String, nullable=True)
    embedding = Column(Vector(3072))
    file_hash = Column(String, index=True) # DO NOT put unique=True here
    page_number = Column(Integer, nullable=True)
    start_time = Column(Float, nullable=True)
    chunk_text = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    mime_type = Column(String, nullable=True)
    __table_args__ = (
        UniqueConstraint('file_hash', 'page_number', name='idx_file_hash_page'),
    )