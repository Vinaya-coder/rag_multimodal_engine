import os
import shutil
import mimetypes
import hashlib
import sqlalchemy

from fastapi import APIRouter, UploadFile, File, Depends, Form, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import settings
from app.drivers.database import get_db
from app.data_models.sql_models import MediaVault
from app.logic.embedder import MultimodalEmbedder
from app.logic.processor import chunk_pdf, get_video_chapters, process_image

router = APIRouter()
embedder = MultimodalEmbedder()



@router.post("/upload")
async def upload_media(
    file: UploadFile = File(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_path = os.path.join(settings.UPLOAD_DIR, file.filename)
    # Save file
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256_hash.update(chunk)
    file_digest = sha256_hash.hexdigest()
    db.query(MediaVault).filter(
        MediaVault.file_hash == file_digest
    ).delete()
    db.commit()
    clean_context = None
    if description and description.strip().lower() not in [
        "string", "undefined", "null", ""
    ]:
        clean_context = description.strip()
    mime_type, _ = mimetypes.guess_type(file_path)
    try:
        if not mime_type:
            raise HTTPException(
                status_code=400,
                detail="Unknown file type"
            )
        if mime_type.startswith("image/"):

            description_text = await process_image(
                file_path, embedder.client,
                embedder.model_id,
                context=clean_context,

            )

            vector = await embedder.get_text_embedding(
                description_text
            )

            db.add(MediaVault(
                filename=file.filename,
                file_url=f"/raw_uploads/{file.filename}",
                embedding=vector,
                description=description_text,
                file_hash=file_digest
            ))

        # ---------------- PDF ----------------
        elif mime_type == "application/pdf":

            chunks = chunk_pdf(file_path)
            texts = [c["text"] for c in chunks]

            embeddings = await embedder.get_batch_embeddings(texts)

            for i, chunk in enumerate(chunks):
                db.add(MediaVault(
                    filename=file.filename,
                    file_url=f"/raw_uploads/{file.filename}",
                    embedding=embeddings[i],
                    description=chunk["text"][:1000],
                    file_hash=file_digest,
                    page_number=chunk["page"],
                    mime_type = mime_type
                ))

        # ---------------- VIDEO ----------------
        elif mime_type.startswith("video/"):

            chapters = await get_video_chapters(file_path,embedder.client,
        embedder.model_id)
            summaries = [s["summary"] for s in chapters]

            embeddings = await embedder.get_batch_embeddings(
                summaries
            )

            for i, segment in enumerate(chapters):
                db.add(MediaVault(
                    filename=file.filename,
                    file_url=f"/raw_uploads/{file.filename}",
                    embedding=embeddings[i],
                    description=segment["summary"],
                    file_hash=file_digest,
                    start_time=float(segment["start_time"]),
                    mime_type=mime_type

                ))
                # ---------------- AUDIO (Song/Humming) ----------------
        elif mime_type.startswith("audio/"):


            audio_file = await embedder.client.aio.files.upload(file=file_path)


            response = await embedder.client.aio.models.generate_content(
                    model=embedder.model_id,
                    contents=[
                        audio_file,
                        "Identify this audio. If it is a song, provide the title and artist. "
                        "Describe the genre, mood, and any specific lyrics. "
                        "If it is humming, describe the melody pattern."
                    ],
                    config={"temperature": 0.0}
            )

            description_text = response.text
            vector = await embedder.get_text_embedding(description_text)

            db.add(MediaVault(
                    filename=file.filename,
                    file_url=f"/raw_uploads/{file.filename}",
                    embedding=vector,
                    description=description_text,
                    file_hash=file_digest,
                    mime_type=mime_type
            ))
        db.commit()

        return {
            "message": "Success",
            "file": file.filename,
            "status": "Indexed"
        }

    except Exception as e:
        db.rollback()

        if os.path.exists(file_path):
            os.remove(file_path)

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


