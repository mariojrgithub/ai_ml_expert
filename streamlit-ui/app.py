import json
import os
import uuid
from typing import Any, Dict, Generator, List

import requests
import streamlit as st


# -------------------------------------------------------------------
# IMPORTANT:
# All UI traffic goes through the Java gateway only.
#
# If Streamlit runs inside Docker Compose, use the service name `api`.
# If Streamlit runs outside Docker, switch these to localhost.
# Override via API_BASE_URL environment variable.
# -------------------------------------------------------------------
_API_BASE = os.environ.get("API_BASE_URL", "http://api:8080")
API_URL = f"{_API_BASE}/api/chat"
STREAM_URL = f"{_API_BASE}/api/chat/stream"

st.set_page_config(
    page_title="Engineering Copilot",
    page_icon="🤖",
    layout="wide",
)

st.title("Engineering Copilot")

# -------------------------------------------------------------------
# Session state
# -------------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "streaming_enabled" not in st.session_state:
    st.session_state.streaming_enabled = True

if "show_citations" not in st.session_state:
    st.session_state.show_citations = True

if "show_warnings" not in st.session_state:
    st.session_state.show_warnings = True

# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    st.write(f"Session ID: `{st.session_state.session_id}`")

    st.session_state.streaming_enabled = st.toggle(
        "Enable streaming",
        value=st.session_state.streaming_enabled,
        help="Use the Java gateway streaming endpoint: /api/chat/stream",
    )

    st.session_state.show_citations = st.checkbox(
        "Show citations",
        value=st.session_state.show_citations,
    )

    st.session_state.show_warnings = st.checkbox(
        "Show warnings",
        value=st.session_state.show_warnings,
    )

    if st.button("New session"):
        st.session_state.session_id = str(uuid.uuid4())
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.subheader("Optional file upload")
    uploaded_files = st.file_uploader(
        "Upload .txt / .md / .pdf files",
        type=["txt", "md", "pdf"],
        accept_multiple_files=True,
        help="This UI block only uploads files in the browser right now. Wire it to a backend ingestion endpoint if you add one.",
    )

    if uploaded_files:
        st.info(f"{len(uploaded_files)} file(s) selected")
        for f in uploaded_files:
            st.write(f"- {f.name} ({f.size} bytes)")

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def stream_gateway_response(session_id: str, prompt: str) -> Generator[Dict, None, None]:
    """
    Streams NDJSON frames from the Java gateway (delivered via SSE).
    Each SSE event carries one JSON object with type: 'meta' | 'delta' | 'done'.
    """
    with requests.post(
        STREAM_URL,
        json={"sessionId": session_id, "message": prompt},
        stream=True,
        timeout=300,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines(decode_unicode=True):
            if not line:
                continue
            # SSE lines arrive as "data: {...}" — strip the prefix.
            # If the gateway sends raw NDJSON instead, the strip is a no-op.
            if line.startswith("data:"):
                line = line[len("data:"):].strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Guard against Jackson double-encoding (String wrapped in JSON quotes)
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except json.JSONDecodeError:
                    continue
            if isinstance(parsed, dict):
                yield parsed


def call_non_streaming(session_id: str, prompt: str) -> Dict[str, Any]:
    response = requests.post(
        API_URL,
        json={"sessionId": session_id, "message": prompt},
        timeout=300,
    )
    response.raise_for_status()
    return response.json()


def render_content(fmt: str, content: Any, language: str | None):
    if fmt == "markdown":
        st.markdown(content)
    elif fmt == "code":
        st.code(content, language=language or "python")
    elif fmt == "json":
        try:
            st.json(json.loads(content) if isinstance(content, str) else content)
        except Exception:
            st.code(content, language="json")
    else:
        st.text(str(content))


# -------------------------------------------------------------------
# Render prior messages
# -------------------------------------------------------------------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_content(
                msg.get("format", "markdown"),
                msg["content"],
                msg.get("language"),
            )
            warnings = msg.get("warnings") or []
            citations = msg.get("citations") or []

            if st.session_state.show_warnings and warnings:
                with st.expander("Warnings"):
                    for w in warnings:
                        st.write(f"- {w}")

            if st.session_state.show_citations and citations:
                with st.expander("Citations"):
                    for c in citations:
                        st.json(c)
        else:
            st.markdown(msg["content"])

# -------------------------------------------------------------------
# Input
# -------------------------------------------------------------------
prompt = st.chat_input("Ask an engineering question")

if prompt:
    # Store + render user message
    user_msg = {
        "role": "user",
        "content": prompt,
    }
    st.session_state.messages.append(user_msg)

    with st.chat_message("user"):
        st.markdown(prompt)

    # Assistant response
    with st.chat_message("assistant"):
        if st.session_state.streaming_enabled:
            try:
                fmt = "markdown"
                language = None
                accumulated = ""
                warnings: List[str] = []
                citations: List[Dict] = []

                placeholder = st.empty()

                for frame in stream_gateway_response(
                    st.session_state.session_id,
                    prompt,
                ):
                    frame_type = frame.get("type")

                    if frame_type == "meta":
                        fmt = frame.get("format", "markdown")
                        language = frame.get("language")

                    elif frame_type == "delta":
                        accumulated += frame.get("content", "")
                        # Show live preview as markdown regardless of final format
                        # so the user sees progressive output
                        placeholder.markdown(accumulated + "▌")

                    elif frame_type == "done":
                        warnings = frame.get("warnings", [])
                        citations = frame.get("citations", [])

                # Replace live preview with final rendered content
                placeholder.empty()
                render_content(fmt, accumulated, language)

                if st.session_state.show_warnings and warnings:
                    with st.expander("Warnings"):
                        for w in warnings:
                            st.write(f"- {w}")

                if st.session_state.show_citations and citations:
                    with st.expander("Citations"):
                        for c in citations:
                            st.json(c)

                assistant_msg = {
                    "role": "assistant",
                    "content": accumulated,
                    "format": fmt,
                    "language": language,
                    "warnings": warnings,
                    "citations": citations,
                }

            except Exception as ex:
                error_text = f"Streaming failed: {ex}"
                st.error(error_text)

                assistant_msg = {
                    "role": "assistant",
                    "content": error_text,
                    "format": "text",
                    "language": None,
                    "warnings": ["Streaming request failed."],
                    "citations": [],
                }

        else:
            try:
                data = call_non_streaming(
                    st.session_state.session_id,
                    prompt,
                )

                content = data.get("content") or data.get("answer") or ""
                fmt = data.get("format", "markdown")
                language = data.get("language")
                warnings = data.get("warnings", [])
                citations = data.get("citations", [])

                render_content(fmt, content, language)

                if st.session_state.show_warnings and warnings:
                    with st.expander("Warnings"):
                        for w in warnings:
                            st.write(f"- {w}")

                if st.session_state.show_citations and citations:
                    with st.expander("Citations"):
                        for c in citations:
                            st.json(c)

                assistant_msg = {
                    "role": "assistant",
                    "content": content,
                    "format": fmt,
                    "language": language,
                    "warnings": warnings,
                    "citations": citations,
                }

            except Exception as ex:
                error_text = f"Request failed: {ex}"
                st.error(error_text)

                assistant_msg = {
                    "role": "assistant",
                    "content": error_text,
                    "warnings": ["Non-streaming request failed."],
                    "citations": [],
                }

    st.session_state.messages.append(assistant_msg)