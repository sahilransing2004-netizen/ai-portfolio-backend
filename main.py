import json
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

from prompts import SYSTEM_PROMPT

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to your Vercel URL once deployed
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

DATA_PATH = Path(__file__).parent / "data" / "candidate_profile.json"
with open(DATA_PATH) as f:
    CANDIDATE_DATA = json.load(f)

class Msg(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Msg]   # <-- matches sahil-os-frontend's { messages: [...] }

@app.post("/chat")
async def chat(req: ChatRequest):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nCandidate data:\n" + json.dumps(CANDIDATE_DATA)},
        *[{"role": m.role, "content": m.content} for m in req.messages],
    ]

    def stream():
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            stream=True,
        )
        for chunk in completion:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    return StreamingResponse(stream(), media_type="text/plain")

@app.get("/health")
def health():
    return {"status": "ok"}