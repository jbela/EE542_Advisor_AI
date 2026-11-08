import uuid
from html import escape
from pathlib import Path
from urllib.parse import urlparse

import requests
import streamlit as st


# ----------------------------------
# Page Configuration
# ----------------------------------
st.set_page_config(
    page_title="USC Advisor AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
LOGO_PATH = BASE_DIR / "assets" / "usc-seal.png"
TOMMY_PATH = BASE_DIR / "assets" / "tommy-avatar.png"

ASSISTANT_AVATAR = (
    str(TOMMY_PATH) if TOMMY_PATH.is_file() else "🎓"
)


# ----------------------------------
# USC Theme
# ----------------------------------
st.markdown(
    """
    <style>
        :root {
            --usc-cardinal: #990000;
            --usc-gold: #FFCC00;
            --usc-bg: #FCFAF7;
            --usc-border: #E8E0D7;
        }

        .stApp {
            background-color: var(--usc-bg);
        }

        /* Reduce excess space above content */
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 2rem;
            max-width: 1150px;
        }

        h1, h2, h3 {
            color: var(--usc-cardinal) !important;
        }

        /* Sidebar */
        section[data-testid="stSidebar"] .stButton button p {
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        /* Buttons */
        .stButton > button {
            border-radius: 9px;
            border: 1px solid #DED6CE;
            background-color: white;
            color: #303030;
            font-weight: 500;
        }

        .stButton > button:hover {
            border-color: var(--usc-cardinal);
            color: var(--usc-cardinal);
        }

        button[kind="primary"],
        button[data-testid="stBaseButton-primary"] {
            background-color: var(--usc-cardinal) !important;
            border-color: var(--usc-cardinal) !important;
            color: white !important;
        }

        button[kind="primary"]:hover,
        button[data-testid="stBaseButton-primary"]:hover {
            background-color: #750000 !important;
        }

        /* Inline citation chips */
        .usc-sources-row {
            display: flex;
            align-items: center;
            flex-wrap: wrap;
            gap: 0.4rem;
            margin-top: 0.65rem;
            padding-bottom: 0.7rem;
            min-height: 2.5rem;
        }

        .usc-sources-label {
            font-size: 0.78rem;
            color: #990000;
            font-weight: 600;
            margin-right: 0.15rem;
        }

        .usc-source-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.2rem 0.55rem;
            font-size: 0.74rem;
            line-height: 1.2;
            background-color: #FFFFFF;
            border: 1px solid #E8E0D7;
            border-radius: 999px;
            color: #990000 !important;
            text-decoration: none !important;
            max-width: 190px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .usc-source-chip:hover {
            background-color: #FFF5F0;
            border-color: #990000;
            color: #990000 !important;
        }

        /* Align chat headings with avatar */
        [data-testid="stChatMessage"] h3 {
            margin-top: 0 !important;
            padding-top: 0 !important;
            margin-bottom: 0.5rem !important;
            font-size: 1.35rem !important;
            line-height: 1.25 !important;
        }

        /* Adjust Tommy avatar position */
        [data-testid="stChatMessageAvatar"]:has(img) {
            margin-top: 6px;
        }

        /* Chat cards */
        [data-testid="stChatMessage"] {
            background-color: white;
            border: 1px solid var(--usc-border);
            border-radius: 12px;
            padding: 0.7rem;
        }

        /* Tommy chat avatar */
        [data-testid="stChatMessageAvatar"] {
            background-color: transparent !important;
            border: none !important;
        }

        [data-testid="stChatMessageAvatar"] img {
            width: 48px !important;
            height: 48px !important;
            object-fit: contain;
            border-radius: 10px;
            background-color: transparent;
        }

        /* Chat input */
        [data-testid="stChatInput"] {
            border-radius: 12px;
        }

        [data-testid="stBottom"] {
            background-color: var(--usc-bg);
        }

        /* Hide deploy button if present */
        .stAppDeployButton,
        [data-testid="stAppDeployButton"] {
            display: none !important;
        }

        footer {
            visibility: hidden;
        }

        hr {
            border-color: var(--usc-border);
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------------
# Session State
# ----------------------------------
def make_chat():
    return {
        "title": "New conversation",
        "messages": [],
    }


if "chats" not in st.session_state:
    first_id = uuid.uuid4().hex
    old_messages = st.session_state.get("messages", [])

    st.session_state.chats = {
        first_id: {
            "title": (
                old_messages[0]["content"][:35]
                if old_messages
                else "New conversation"
            ),
            "messages": list(old_messages),
        }
    }
    st.session_state.active_chat_id = first_id

if (
    "active_chat_id" not in st.session_state
    or st.session_state.active_chat_id
    not in st.session_state.chats
):
    st.session_state.active_chat_id = next(
        iter(st.session_state.chats)
    )


def current_chat():
    return st.session_state.chats[
        st.session_state.active_chat_id
    ]


def new_chat():
    if not current_chat()["messages"]:
        return

    chat_id = uuid.uuid4().hex
    st.session_state.chats[chat_id] = make_chat()
    st.session_state.active_chat_id = chat_id


def open_chat(chat_id):
    st.session_state.active_chat_id = chat_id


# ----------------------------------
# Mock Responses
# TODO: Connect Jia's FastAPI backend
# ----------------------------------
def get_mock_response(question: str) -> str:
    q = question.lower()

    if "d-clearance" in q or "d clearance" in q:
        return (
            "### D-Clearance Guidance\n\n"
            "**Demo response — not verified USC advice.**\n\n"
            "The final assistant will retrieve current USC "
            "D-Clearance procedures and provide official "
            "source links."
        )

    if "prerequisite" in q or "corequisite" in q:
        return (
            "### Prerequisite Information\n\n"
            "**Demo response — not verified USC advice.**\n\n"
            "The final assistant will check the latest "
            "USC Catalog and Schedule of Classes for "
            "course requirements."
        )

    if "cloud" in q or "career" in q:
        return (
            "### Course Recommendations\n\n"
            "**Demo response — not verified USC advice.**\n\n"
            "The final assistant will analyze course "
            "descriptions and syllabi to recommend "
            "USC courses aligned with your career interests."
        )

    return (
        "### Academic Advising Assistant\n\n"
        "**This is a simulated AI response.**\n\n"
        "Once the RAG backend is connected, responses "
        "will be generated from USC academic sources "
        "with supporting citations."
    )

# ----------------------------------
# FastAPI Integration
# ----------------------------------
API_URL = "http://127.0.0.1:8000/ask"


def get_api_response(question: str) -> dict:
    try:
        response = requests.post(
            API_URL,
            json={"question": question},
            timeout=130,
        )
        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict) or not isinstance(
            data.get("answer"), str
        ):
            raise ValueError("Invalid API response format")

        sources = data.get("sources", [])

        if not isinstance(sources, list):
            sources = []

        return {
            "answer": data["answer"],
            "sources": sources,
            "status": data.get("status", "unknown"),
        }

    except (requests.exceptions.RequestException, ValueError) as e:
        return {
            "answer": (
                "⚠️ Unable to get an AI response from the backend.\n\n"
                f"Error: {type(e).__name__}: {e}\n\n"
                "Please check whether FastAPI and Ollama "
                "are running."
            ),
            "sources": [],
            "status": "error",
        }

# ----------------------------------
# Sidebar
# ----------------------------------
with st.sidebar:
    st.markdown("### USC Advisor AI")
    st.caption("Academic Advising Assistant")
    st.divider()

    st.markdown("**Recent Chats**")

    for chat_id, chat_data in reversed(
        list(st.session_state.chats.items())
    ):
        is_active = (
            chat_id == st.session_state.active_chat_id
        )

        title = chat_data["title"]

        if len(title) > 23:
            title = title[:23] + "..."

        if st.button(
            f"💬 {title}",
            key=f"chat_{chat_id}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            open_chat(chat_id)
            st.rerun()

    st.divider()

    st.markdown("**Response Mode**")

    response_mode = st.radio(
        "Select response mode",
        ["Demo", "API"],
        horizontal=True,
        label_visibility="collapsed",
    )

    st.divider()
    st.caption("EE542 Final Project · Fall 2026")
    st.caption("Jia, Ellie, Isabel")
    st.caption("Prototype version")


# ----------------------------------
# Main Header
# ----------------------------------
logo_col, title_col, button_col = st.columns(
    [1.2, 5.5, 1.3],
    vertical_alignment="center",
)

with logo_col:
    if LOGO_PATH.is_file():
        st.image(str(LOGO_PATH), width=90)
    else:
        st.markdown("### USC")

with title_col:
    st.title("USC Advisor AI")
    st.caption(
        "Your AI-powered Academic Advising Assistant"
    )

with button_col:
    if st.button(
        "＋ New Chat",
        type="primary",
        key="new_chat_button",
    ):
        new_chat()
        st.rerun()


if response_mode == "Demo":
    st.caption(
        "⚠️ Demo mode — Responses are simulated, "
        "not official academic advice."
    )
else:
    st.caption(
        "⚠️ API mode — AI responses are not yet "
        "verified against official USC sources."
    )


# ----------------------------------
# Suggested Questions
# Always visible, even after chatting
# ----------------------------------
st.markdown("**Suggested Questions**")

example_questions = [
    ("Cloud Engineering Courses",
     "Which USC courses are relevant to cloud engineering?"),
    ("EE 542 Prerequisites",
     "What are the prerequisites for EE 542?"),
    ("D-Clearance Guidance",
     "How does D-Clearance work?"),
]

columns = st.columns(3, gap="small")
selected_question = None

for i, (label, question) in enumerate(example_questions):
    with columns[i]:
        if st.button(
            label,
            key=f"example_{i}",
            use_container_width=True,
        ):
            selected_question = question

st.divider()


# ----------------------------------
# Current Conversation
# ----------------------------------
chat = current_chat()
messages = chat["messages"]


# ----------------------------------
# Welcome Message for Empty Chats
# ----------------------------------
if not messages:
    st.markdown("### How can I help you today?")

    st.write(
        "Explore USC courses, understand academic "
        "requirements, and plan your studies "
        "around your career goals."
    )


# ----------------------------------
# Display Chat History + Source Chips
# ----------------------------------
for message in messages:
    avatar = (
        ASSISTANT_AVATAR
        if message["role"] == "assistant"
        else "👤"
    )

    with st.chat_message(
        message["role"],
        avatar=avatar,
    ):
        st.markdown(message["content"])

        # Display citation chips for assistant messages
        if message["role"] == "assistant":
            sources = message.get("sources") or []
            status = message.get("status", "unknown")

            if not isinstance(sources, list):
                sources = []

            source_chips = []

            for i, source in enumerate(sources, start=1):
                if not isinstance(source, dict):
                    continue

                url = source.get("url")

                if not isinstance(url, str):
                    continue

                try:
                    parsed = urlparse(url)

                    if (
                        parsed.scheme not in ("http", "https")
                        or not parsed.hostname
                    ):
                        continue

                except ValueError:
                    continue

                title = str(
                    source.get("title") or f"Source {i}"
                )

                # Short label, full title on hover
                label = (
                    title[:21] + "…"
                    if len(title) > 22
                    else title
                )

                source_chips.append(
                    f'<a class="usc-source-chip" '
                    f'href="{escape(url, quote=True)}" '
                    f'title="{escape(title, quote=True)}" '
                    f'target="_blank" '
                    f'rel="noopener noreferrer">'
                    f'↗ {escape(label)}</a>'
                )

            if source_chips:
                chips_html = "".join(source_chips)

                st.markdown(
                    '<div class="usc-sources-row">'
                    '<span class="usc-sources-label">'
                    'Sources'
                    '</span>'
                    f'{chips_html}'
                    '</div>',
                    unsafe_allow_html=True,
                )

            elif status not in ("demo", "error"):
                st.caption(
                    "No supporting sources available yet."
                )

# ----------------------------------
# Chat Input
# ----------------------------------
user_input = st.chat_input(
    "Ask me anything about USC courses..."
)

prompt = user_input or selected_question

if prompt:
    if not messages:
        chat["title"] = (
            prompt[:35] + "..."
            if len(prompt) > 35
            else prompt
        )

    messages.append({
        "role": "user",
        "content": prompt,
    })

    # Select response source
    if response_mode == "API":
        with st.spinner("USC Advisor AI is thinking..."):
            result = get_api_response(prompt)
    else:
        result = {
            "answer": get_mock_response(prompt),
            "sources": [],
            "status": "demo",
        }

    messages.append({
        "role": "assistant",
        "content": result["answer"],
        "sources": result["sources"],
        "status": result["status"],
    })

    st.rerun()