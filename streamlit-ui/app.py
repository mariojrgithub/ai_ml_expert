import json
import os
import time
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
LOGIN_URL = f"{_API_BASE}/api/auth/login"

st.set_page_config(
    page_title="Engineering Copilot",
    page_icon="🤖",
    layout="wide",
)

# -------------------------------------------------------------------
# Session state
# -------------------------------------------------------------------
if "auth_token" not in st.session_state:
    st.session_state.auth_token = None

if "auth_expires_at" not in st.session_state:
    st.session_state.auth_expires_at = 0.0

if "auth_username" not in st.session_state:
    st.session_state.auth_username = ""

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
# Auth helpers
# -------------------------------------------------------------------
def _auth_headers() -> Dict[str, str]:
    """Return Authorization header dict if a token is present."""
    if st.session_state.auth_token:
        return {"Authorization": f"Bearer {st.session_state.auth_token}"}
    return {}


def _token_is_valid() -> bool:
    """True if a token exists and has not expired (with 30 s grace)."""
    return (
        bool(st.session_state.auth_token)
        and time.time() < st.session_state.auth_expires_at - 30
    )


def _clear_auth() -> None:
    st.session_state.auth_token = None
    st.session_state.auth_expires_at = 0.0
    st.session_state.auth_username = ""


def do_login(username: str, password: str) -> bool:
    """POST to /api/auth/login; store the returned JWT. Returns True on success."""
    try:
        resp = requests.post(
            LOGIN_URL,
            json={"username": username, "password": password},
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token") or data.get("accessToken") or data.get("access_token")
            if token:
                # The API returns expiresIn (ms) or we default to 1 hour
                expires_in_ms = data.get("expiresIn", 3_600_000)
                st.session_state.auth_token = token
                st.session_state.auth_expires_at = time.time() + expires_in_ms / 1000.0
                st.session_state.auth_username = username
                return True
        return False
    except requests.RequestException:
        return False


# -------------------------------------------------------------------
# Login gate — show login page if not authenticated
# -------------------------------------------------------------------
if not _token_is_valid():
    _clear_auth()
    st.title("Engineering Copilot — Sign In")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign In")
        if submitted:
            if do_login(username, password):
                st.rerun()
            else:
                st.error("Invalid username or password.")
    st.stop()


st.title("Engineering Copilot")

# -------------------------------------------------------------------
# Sidebar
# -------------------------------------------------------------------
with st.sidebar:
    st.header("Settings")
    st.write(f"Signed in as: **{st.session_state.auth_username}**")
    st.write(f"Session ID: `{st.session_state.session_id}`")

    if st.button("Sign Out"):
        _clear_auth()
        st.rerun()

    st.divider()

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
    correlation_id = str(uuid.uuid4())
    with requests.post(
        STREAM_URL,
        json={"sessionId": session_id, "message": prompt},
        headers={**_auth_headers(), "X-Correlation-ID": correlation_id},
        stream=True,
        timeout=300,
    ) as response:
        if response.status_code == 401:
            _clear_auth()
            st.rerun()
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
    correlation_id = str(uuid.uuid4())
    response = requests.post(
        API_URL,
        json={"sessionId": session_id, "message": prompt},
        headers={**_auth_headers(), "X-Correlation-ID": correlation_id},
        timeout=300,
    )
    if response.status_code == 401:
        _clear_auth()
        st.rerun()
    response.raise_for_status()
    return response.json()


def render_content(fmt: str, content: Any, language: str | None, *, container=None):
    """Render content in the given container (defaults to the main page).

    When fmt='code', the LLM typically returns a full markdown document that
    wraps the code in triple-backtick fences together with prose sections.
    In that case we fall back to markdown so the formatting is preserved.
    Pure bare-code strings (no fences) still use st.code for syntax highlighting.
    """
    out = container if container is not None else st
    if fmt == "markdown":
        out.markdown(content)
    elif fmt == "code":
        # LLM-generated code responses contain markdown structure (headers + fences).
        # Render as markdown so fences and prose display correctly.
        if isinstance(content, str) and "```" in content:
            out.markdown(content)
        else:
            out.code(content, language=language or "python")
    elif fmt == "json":
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
            # st.empty() placeholders don't support .json(); always use main page
            st.json(parsed)
        except Exception:
            out.code(content, language="json")
    else:
        out.text(str(content))


# -------------------------------------------------------------------
# Render prior messages
# -------------------------------------------------------------------
for _msg_idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            render_content(
                msg.get("format", "markdown"),
                msg["content"],
                msg.get("language"),
            )
            _replay_warnings = msg.get("warnings") or []
            _replay_citations = msg.get("citations") or []

            if st.session_state.show_warnings and _replay_warnings:
                with st.expander("Warnings", expanded=False, key=f"warnings_{_msg_idx}"):
                    for w in _replay_warnings:
                        st.write(f"- {w}")

            if st.session_state.show_citations and _replay_citations:
                with st.expander("Citations", expanded=False, key=f"citations_{_msg_idx}"):
                    for c in _replay_citations:
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
                stream_error: str | None = None
                saw_done = False

                placeholder = st.empty()
                placeholder.info("⏳ Routing your request...")

                for frame in stream_gateway_response(
                    st.session_state.session_id,
                    prompt,
                ):
                    frame_type = frame.get("type")

                    if frame_type == "meta":
                        fmt = frame.get("format", "markdown")
                        language = frame.get("language")
                        intent = frame.get("intent", "")
                        if intent in ("QA",):
                            placeholder.info("🔍 Retrieving context...")
                        elif intent in ("CODE", "SQL", "MONGO"):
                            placeholder.info(f"⚙️ Generating {intent} response...")
                        else:
                            placeholder.info("🧠 Generating response...")

                    elif frame_type == "delta":
                        if not accumulated:  # First chunk, clear loading message
                            placeholder.empty()
                        accumulated += frame.get("content", "")
                        # Show live preview as markdown regardless of final format
                        # so the user sees progressive output
                        placeholder.markdown(accumulated + "▌")

                    elif frame_type == "done":
                        saw_done = True
                        warnings = frame.get("warnings", [])
                        citations = frame.get("citations", [])
                        break

                    elif frame_type == "error":
                        stream_error = frame.get("message", "Streaming failed.")
                        break

                # Replace the live-preview cursor with the final rendered content.
                # We reuse the placeholder widget so the content stays in the correct
                # DOM position and the cursor (▌) is cleanly replaced.
                if stream_error:
                    placeholder.error(stream_error)
                    warnings = warnings + ["Streaming returned an error frame."]
                    accumulated = stream_error
                    fmt = "text"
                    language = None
                elif not accumulated and not saw_done:
                    fallback = "No output was produced by the stream."
                    placeholder.warning(fallback)
                    warnings = warnings + [fallback]
                    accumulated = fallback
                    fmt = "text"
                    language = None
                else:
                    render_content(fmt, accumulated, language, container=placeholder)

                if st.session_state.show_warnings and warnings:
                    with st.expander("Warnings", expanded=False, key="warnings_streaming"):
                        for w in warnings:
                            st.write(f"- {w}")

                if st.session_state.show_citations and citations:
                    with st.expander("Citations", expanded=False, key="citations_streaming"):
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
                error_id = str(uuid.uuid4())[:8]
                st.error(
                    f"Something went wrong while generating the response. "
                    f"Please try again. (Error ID: `{error_id}`)"
                )

                assistant_msg = {
                    "role": "assistant",
                    "content": f"[Error ID: {error_id}] A streaming error occurred.",
                    "format": "text",
                    "language": None,
                    "warnings": ["Streaming request failed."],
                    "citations": [],
                }

        else:
            placeholder = st.empty()
            placeholder.info("🔄 Fetching response...")
            
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

                render_content(fmt, content, language, container=placeholder)

                if st.session_state.show_warnings and warnings:
                    with st.expander("Warnings", expanded=False, key="warnings_nonstreaming"):
                        for w in warnings:
                            st.write(f"- {w}")

                if st.session_state.show_citations and citations:
                    with st.expander("Citations", expanded=False, key="citations_nonstreaming"):
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
    st.rerun()