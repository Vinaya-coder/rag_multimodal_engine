import PIL.Image
import fitz
import json
import asyncio
from google.genai import types
from app.core.config import settings


async def process_image(file_path: str, client, model_id, **kwargs):
    file = await client.aio.files.upload(file=file_path)

    clean_context = kwargs.get('context', 'No specific context.')

    prompt = f"""
    Analyze this image for a Multimodal AI Agent.
    Rules to follow: {clean_context}

    Return JSON: {{
      "type": "image",
      "primary_subject": "main object or person",
      "visual_details": "colors, setting, background",
      "actions": "what is happening"
    }}
    """

    response = await client.aio.models.generate_content(
        model=model_id,
        contents=[file, prompt],
        config={
            "temperature": 0.0,
            "response_mime_type": "application/json"
        }
    )
    return response.text

def chunk_pdf(file_path):
    doc = fitz.open(file_path)
    chunks = []
    for page in doc:
        page_text = " ".join([b[4] for b in page.get_text("blocks") if b[4].strip()])
        if page_text.strip():
            chunks.append({"page": page.number + 1, "text": page_text.strip()})
    return chunks


async def get_video_chapters(file_path: str, client, model_id):
    video_file = await client.aio.files.upload(file=file_path)

    while True:
        video_file = await client.aio.files.get(name=video_file.name)
        if video_file.state.name == "ACTIVE":
            break
        await asyncio.sleep(5)

    prompt = """
    Break video into 15s segments. Return JSON ONLY.
    Structure: [{
      "start_time": float (total seconds),
      "summary": "Detailed visual description of this segment for an AI Agent"
    }]
    """

    response = await client.aio.models.generate_content(
        model=model_id,
        contents=[video_file, prompt],
        config=types.GenerateContentConfig(response_mime_type="application/json")
    )

    await client.aio.files.delete(name=video_file.name)
    return json.loads(response.text)


async def process_audio_file(file_path: str, client, model_id):
    audio_file = await client.aio.files.upload(file=file_path)

    # 1. Define the prompt clearly
    prompt = """Transcribe this audio clip word-for-word.
Return ONLY the spoken text.
If nothing understandable is spoken, return an empty string.
"""


    response = await client.aio.models.generate_content(
        model=model_id,
        contents=[audio_file, prompt],
        config={"temperature":0.0}
    )
    print("TRANSCRIPT:", response.text)
    return response.text