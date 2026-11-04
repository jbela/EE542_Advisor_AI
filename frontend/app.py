
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="USC Advisor AI",
    page_icon="🎓",
    layout="wide"
)

# Title
st.title("🎓 USC Advisor AI")
st.caption("Your AI-powered Academic Advising Assistant")

st.divider()

# Welcome message
st.subheader("Welcome to USC Advisor AI!")

st.write(
    "Explore USC courses, understand academic requirements, "
    "and plan your studies based on your career goals."
)

# Example questions
st.subheader("What can I help you with?")

st.info("Which USC courses are relevant to cloud engineering?")
st.info("What are the prerequisites for EE 542?")
st.info("How does D-Clearance work?")

# Chat input
question = st.chat_input("Ask me anything about USC courses...")

if question:
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        st.write(
            "This is a demo response. "
            "The AI backend will be connected later."
        )
