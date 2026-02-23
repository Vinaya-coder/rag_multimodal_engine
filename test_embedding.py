import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

# The new SDK is cleaner; it looks for GEMINI_API_KEY automatically
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

print("--- Checking Access ---")
try:
    # Use the new 2026 standard model
    result = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents="A cat sitting on a beach"
    )

    # In the new SDK, 'result.embeddings' is a list of objects
    vector = result.embeddings[0].values
    print(f"✅ Success! Vector Length: {len(vector)}")
    print(f"First 5 values: {vector[:5]}")

except Exception as e:
    print(f"❌ Connection Failed: {e}")