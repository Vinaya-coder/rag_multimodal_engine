import streamlit as st
import requests

# --- CONFIGURATION ---
SERVER_HOST = "127.0.0.1:8000"
BASE_URL = "http://localhost:8000/api/v1"
INGEST_URL = f"{BASE_URL}/ingestion/upload"
SEARCH_URL = f"{BASE_URL}/discovery/search"

st.set_page_config(page_title="Multimodal RAG Engine", layout="wide", page_icon="🧠")


# --- HELPER FUNCTIONS ---
def decimal_to_total_seconds(decimal_time):
    try:
        if decimal_time is None: return 0
        minutes = int(decimal_time)
        # Extract the decimal part and treat as seconds
        seconds = round((float(decimal_time) - minutes) * 100)
        return (minutes * 60) + seconds
    except Exception:
        return 0

st.title("🧠 Multimodal RAG Engine")
with st.sidebar:
    st.header("📤 Data Ingestion")
    uploaded_file = st.file_uploader("Upload Media", type=['mp4', 'pdf', 'jpg', 'png', 'jpeg'])
    user_description = st.text_area("Context (Optional)", placeholder="Search Engine")

    if uploaded_file and st.button("🚀 Process & Index"):
        with st.status("Indexing...", expanded=True) as status:
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}
                data = {"description": user_description if user_description.strip() else "string"}
                r = requests.post(INGEST_URL, files=files, data=data)
                if r.status_code == 200:
                    status.update(label="✅ Success!", state="complete", expanded=False)
                    st.success(f"Added {uploaded_file.name}")
                else:
                    status.update(label="❌ Failed", state="error")
                    st.error(f"Error: {r.text}")
            except Exception as e:
                st.error(f"Connection Error: {e}")

# --- MAIN: SEARCH ---
# --- MAIN: SEARCH ---
query = st.text_input("🔍 Search your vault:", placeholder="e.g. when did he put the water into cup")

if query:
    with st.spinner("Searching..."):
        try:
            response = requests.get(SEARCH_URL, params={"q": query})
            res_data = response.json()

            # 1. AI Analysis Section (Matching your screenshot style)
            st.subheader("🤖 AI Analysis")
            st.info(res_data.get("answer", "No answer generated."))

            # 2. Relevant Sources (Direct Full-Width View)
            st.subheader("📍 Relevant Sources")
            sources = res_data.get("sources", [])

            if not sources:
                st.warning("No matches found. Try lowering the threshold in your FastAPI code.")
            else:
                # We remove the "cols = st.columns(2)" to let images be big like your photo
                for src in sources:
                    with st.container(border=True):
                        # Construct URL to your FastAPI server
                        full_media_url = f"http://{SERVER_HOST}{src.get('url', '')}"

                        if src.get("start_time") is not None:
                            # Big Video Player
                            t_sec = decimal_to_total_seconds(src['start_time'])
                            st.video(full_media_url, start_time=int(t_sec))
                            st.caption(f"🎥 Video Segment at {src['start_time']} seconds")

                        elif src.get("page") is not None:
                            # PDF Link
                            st.info(f"📄 PDF Document - Page {src['page']}")
                            st.link_button("View Full Page", full_media_url)

                        else:
                            # Big, Clear Image (Fixing the warning here too)
                            st.image(full_media_url, width='stretch')
                            st.caption(f"🖼 Image Match: {src.get('filename')}")

                        # Optional Metadata below the image
                        st.write(f"**Confidence Score:** `{src.get('confidence')}`")
                        st.divider()  # Adds a nice line between different results

        except Exception as e:
            st.error(f"Search failed: {e}")
# --- FOOTER ---
st.divider()
st.caption("Powered by FastAPI + Streamlit + Gemini 2.0")