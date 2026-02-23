import os
import yaml
import json
import sqlalchemy
from typing import Union
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.drivers.database import get_db
from app.logic.embedder import MultimodalEmbedder

router = APIRouter()
embedder = MultimodalEmbedder()

# Load rules safely
try:
    with open("agent_manifest.yaml", "r") as f:
        manifest = yaml.safe_load(f)
        agent_rules = manifest['agent_config']['orchestration']['rules']
except Exception as e:
    agent_rules = "Generic relevancy rules."


@router.get("/files")
async def list_vault_files(db: Session = Depends(get_db)):
    stmt = text("""
        SELECT DISTINCT ON (filename) filename, file_url, created_at 
        FROM media_vault 
        ORDER BY filename, created_at DESC
    """)
    results = db.execute(stmt).fetchall()
    return [{"filename": r[0], "url": r[1]} for r in results]


@router.get("/search")
async def semantic_search(q: str, history: str = "", db: Session = Depends(get_db)):
    query_vector = await embedder.get_text_embedding(q)
    vector_str = str(query_vector if isinstance(query_vector, list) else query_vector.tolist())

    stmt = text("""
        SELECT filename, file_url, description, 
               1 - (embedding <=> CAST(:v AS vector)) AS similarity,
               page_number, start_time
        FROM media_vault
        WHERE 1 - (embedding <=> CAST(:v AS vector)) > 0.55
        ORDER BY similarity DESC
        LIMIT 10
    """)

    db_results = db.execute(stmt, {"v": vector_str}).fetchall()

    if not db_results:
        return {"sources": []}

    candidates = [{"id": i, "content": r[2], "filename": r[0]} for i, r in enumerate(db_results)]

    gate_prompt = f"""
    Rules: {agent_rules}
    User Query: "{q}"
    Available Data: {json.dumps(candidates)}

    Task: 
    Return a JSON list of ALL indices that match the query.
    If there are multiple matches (e.g., multiple images of the same person), include EVERY valid index.
    Do not limit yourself to just one result.
    1. Apply the intent rules. If the user wants a song, ignore images.
    2. Return ONLY a JSON list of indices (e.g., [0, 2, 3]) that strictly match.
    """

    gate_resp = await embedder.client.aio.models.generate_content(
        model=embedder.model_id,
        contents=[gate_prompt],
        config={"response_mime_type": "application/json"}
    )

    try:
        valid_indices = json.loads(gate_resp.text)
        if isinstance(valid_indices, dict): valid_indices = valid_indices.get("indices", [0])
    except:
        valid_indices = [i for i in range(len(db_results))]

    sources = []
    for idx, row in enumerate(db_results):
        if idx in valid_indices:
            sources.append({
                "filename": row[0],
                "url": row[1],
                "confidence": round(float(row[3]), 4),
                "page": row[4],
                "start_time": row[5]
            })

    return {"sources": sources}


@router.post("/search_audio")
async def search_audio(file: UploadFile = File(...), db: Session = Depends(get_db)):
    temp_path = f"temp_{file.filename}"
    with open(temp_path, "wb") as buffer:
        buffer.write(await file.read())

    try:
        audio_file = await embedder.client.aio.files.upload(file=temp_path)
        resp = await embedder.client.aio.models.generate_content(
            model=embedder.model_id,
            contents=[audio_file, "Extract only the main keywords or song title from this audio."],
            config={"temperature": 0.0}
        )
        return await semantic_search(q=resp.text, db=db)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.delete("/delete/{filename}")
async def delete_file(filename: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("DELETE FROM media_vault WHERE filename = :f"), {"f": filename})
        db.commit()
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
        return {"message": f"Deleted {filename}"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))