
from fastapi import FastAPI
from pydantic import BaseModel
import httpx

app = FastAPI()

MODEL = "qwen2.5:3b"
URL = "http://127.0.0.1:11434/api/chat"


class Question(BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask")
async def ask(data: Question):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a prototype academic assistant. "
                "Do not invent USC policies or requirements. "
                "Without official sources, explain that "
                "your response has not been verified."
            )
        },
        {
            "role": "user",
            "content": data.question
        }
    ]

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            URL,
            json={
                "model": MODEL,
                "messages": messages,
                "stream": False
            }
        )
        response.raise_for_status()

    return {
        "answer": response.json()["message"]["content"],
        "sources": [],
        "status": "review_required"
    }
