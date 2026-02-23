import os
import asyncio
import mimetypes
import hashlib
from sqlalchemy.orm import Session
from app.drivers.database import SessionLocal
from app.data_models.sql_models import MediaVault
from app.logic.embedder import MultimodalEmbedder
from app.logic.processor import chunk_pdf, get_video_chapters, process_image

UPLOAD_DIR = "file_vault/raw_uploads"

async def recover_database():
    db = SessionLocal()
    embedder = MultimodalEmbedder()

    print("⚠️  Wiping existing database records...")
    db.query(MediaVault).delete()
    db.commit()

    files = [f for f in os.listdir(UPLOAD_DIR) if os.path.isfile(os.path.join(UPLOAD_DIR, f))]
    print(f"Found {len(files)} files to re-index.")

    for filename in files:
        file_path = os.path.join(UPLOAD_DIR, filename)
        mime_type, _ = mimetypes.guess_type(file_path)

        # Calculate Hash
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                sha256_hash.update(chunk)
        file_digest = sha256_hash.hexdigest()

        print(f"Indexing: {filename} ({mime_type})")

        try:
            # --- IMAGE RECOVERY ---
            if mime_type and mime_type.startswith("image/"):
                desc = await process_image(file_path)
                vec = await embedder.get_text_embedding(desc)
                db.add(MediaVault(
                    filename=filename,
                    file_url=f"/vault/raw_uploads/{filename}",
                    embedding=vec,
                    description=desc,
                    file_hash=file_digest
                ))

            # --- PDF RECOVERY ---
            elif mime_type == "application/pdf":
                chunks = chunk_pdf(file_path)
                texts = [c["text"] for c in chunks]
                embeddings = await embedder.get_batch_embeddings(texts)
                for i, chunk in enumerate(chunks):
                    db.add(MediaVault(
                        filename=filename,
                        file_url=f"/vault/raw_uploads/{filename}",
                        embedding=embeddings[i],
                        description=chunk["text"][:1000],
                        file_hash=file_digest,
                        page_number=chunk["page"]
                    ))

            # --- VIDEO RECOVERY ---
            elif mime_type and mime_type.startswith("video/"):
                chapters = await get_video_chapters(file_path)
                summaries = [s["summary"] for s in chapters]
                embeddings = await embedder.get_batch_embeddings(summaries)
                for i, segment in enumerate(chapters):
                    db.add(MediaVault(
                        filename=filename,
                        file_url=f"/vault/raw_uploads/{filename}",
                        embedding=embeddings[i],
                        description=segment["summary"],
                        file_hash=file_digest,
                        start_time=float(segment["start_time"])
                    ))

            db.commit()
            print(f"✅ Successfully re-indexed {filename}")

        except Exception as e:
            db.rollback()
            print(f"❌ Failed to process {filename}: {e}")

    db.close()
    print("✨ Recovery Complete!")

if __name__ == "__main__":
    asyncio.run(recover_database())