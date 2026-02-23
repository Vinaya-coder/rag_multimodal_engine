from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import ingestion, discovery
import os

app = FastAPI(
    title="Multimodal RAG Engine",
    description="Search through images and PDFs using Gemini Embeddings and pgvector",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("file_vault/raw_uploads", exist_ok=True)
app.mount("/raw_uploads", StaticFiles(directory="file_vault/raw_uploads"), name="raw_uploads")
app.include_router(ingestion.router, prefix="/api/v1/ingestion", tags=["Ingestion"])
app.include_router(discovery.router, prefix="/api/v1/discovery", tags=["Discovery"])

@app.get("/")
async def health_check():
    return {"status": "online", "engine": "Gemini-Multimodal-RAG"}