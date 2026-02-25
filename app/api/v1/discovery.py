import os
import yaml
import json
import asyncio
import sqlalchemy
from typing import Union
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text
from google.genai.errors import ServerError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.drivers.database import get_db
from app.logic.embedder import MultimodalEmbedder
import time
router = APIRouter()
embedder = MultimodalEmbedder()

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
    If a user asks for 'fruits' and an item is 'flowers', EXCLUDE IT.
    Be exhaustive: if there are 5 fruit images, return all 5.
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

MIN_AUDIO_SIZE_BYTES = 1000
from fastapi.responses import JSONResponse


@router.post("/transcribe_chunk")
async def transcribe_chunk(file: UploadFile = File(...)):
    # Create the path inside the function so it's unique
    ts = int(time.time() * 1000)
    temp_path = f"audio_{ts}.webm"
    audio_file = None

    try:
        content = await file.read()

        # FIX 1: Lower the threshold. 100kb was skipping 3-second clips.
        if len(content) < 2000:
            return JSONResponse(content={"text": ""})

        with open(temp_path, "wb") as buffer:
            buffer.write(content)

        # FIX 2: Explicitly handle Gemini upload
        audio_file = await embedder.client.aio.files.upload(file=temp_path)

        is_ready = False
        for _ in range(15):
            audio_file = await embedder.client.aio.files.get(name=audio_file.name)
            if audio_file.state.name == "ACTIVE":
                is_ready = True
                break
            await asyncio.sleep(0.5)

        if not is_ready:
            return JSONResponse(content={"text": ""})

        # FIX 3: Catch Gemini's specific "Internal 500" errors
        try:
            resp = await embedder.client.aio.models.generate_content(
                model=embedder.model_id,
                contents=[audio_file, "Output only the transcript."]
            )
            return JSONResponse(content={"text": resp.text.strip() if resp.text else ""})
        except Exception as gemini_err:
            print(f"Gemini processing failed: {gemini_err}")
            return JSONResponse(content={"text": ""})

    except Exception as e:
        print(f"Global Fallback Error: {e}")
        # ALWAYS return a 200 status with valid JSON so React doesn't crash
        return JSONResponse(content={"text": ""}, status_code=200)

    finally:
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        if audio_file:
            try:
                await embedder.client.aio.files.delete(name=audio_file.name)
            except:
                pass
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