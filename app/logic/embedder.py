import asyncio
import PIL.Image
import json
import re
from google import genai
from google.genai import types
from app.core.config import settings


class MultimodalEmbedder:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_id = "gemini-2.5-flash"
        self.embed_model = "gemini-embedding-001"

    async def get_text_embedding(self, text: str):
        response = await self.client.aio.models.embed_content(
            model=self.embed_model,
            contents=text[:8000],
            config=types.EmbedContentConfig(output_dimensionality=3072)
        )
        return response.embeddings[0].values

    async def generate_answer(self, question: str, contexts: list):
        context_items = []
        for c in contexts:
            if c.get('start_time') is not None:
                location = f"Timestamp: {c['start_time']}s"
            else:
                location = f"Page: {c.get('page', 'Unknown')}"

            context_items.append(
                f"Source: {c['filename']} | Loc: {location}\n"
                f"Content: {c['text']}"
            )

        context_block = "\n---\n".join([
            f"Source: {c['filename']} | "
            f"Loc: {'Page ' + str(c['page']) if c.get('page') else str(c.get('start_time')) + 's'}\n"
            f"Content: {c['text']}"
            for c in contexts
        ])


        prompt = f"""
        USER_QUERY: {question}
        CONTEXT: {context_block}

        TASK: Provide a ONE-SENTENCE direct answer based ONLY on the context. 
        - Do NOT explain your reasoning.
        - Do NOT provide a summary.
        - If you don't know, say "Information not found."
        - Maximum 20 words.
        You are a local vault assistant. Answer the user's question ONLY using the following context. 
        If the information is not in the context,just search for relatable content if not strictly say "I don't have that information in my vault."
        Do NOT talk about conferences, organizers, or anything outside the context.
        """

        response = await self.client.aio.models.generate_content(
            model=self.model_id,
            contents=prompt
        )
        return response.text

    async def get_batch_embeddings(self, texts: list[str]):
        if not texts:
            return []

        all_embeddings = []
        for i in range(0, len(texts), 100):
            batch = texts[i:i + 100]

            response = await self.client.aio.models.embed_content(
                model=self.embed_model,
                contents=batch,
                config=types.EmbedContentConfig(output_dimensionality=3072)
            )

            batch_values = [e.values for e in response.embeddings]
            all_embeddings.extend(batch_values)

        return all_embeddings

    async def get_video_chapters(self, file_path: str):
        client = self.client
        video_file = await client.aio.files.upload(file=file_path)

        while True:
            video_file = await client.aio.files.get(name=video_file.name)
            if video_file.state.name == "ACTIVE":
                break
            elif video_file.state.name == "FAILED":
                raise Exception("Gemini video processing failed.")
            await asyncio.sleep(5)

        prompt = """
        Break this video into 15s segments. 
        For 'start_time', use a decimal format where the whole number is minutes and the decimal is seconds.

        Rules:
        - 12 seconds = 0.12
        - 1 minute and 28 seconds = 1.28
        - 2 minutes and 44 seconds = 2.44
        - IMPORTANT: Never let the decimal part go above .59 (e.g., 1.60 is WRONG, it should be 2.00).

        Return JSON: [{'start_time': float, 'summary': str}]
        """

        try:
            response = client.models.generate_content(
                model=self.model_id,
                contents=[video_file, prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            await client.aio.files.delete(name=video_file.name)

            return json.loads(response.text)

        except Exception as e:
            await client.aio.files.delete(name=video_file.name)
            print(f"Generation Error: {e}")
            raise e