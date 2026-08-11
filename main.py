import json
import os
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv
from pypdf import PdfReader
import io

from prompts import SYSTEM_PROMPT

load_dotenv()

UPLOAD_PASSWORD = os.getenv("UPLOAD_PASSWORD")

SCHEMA_INSTRUCTIONS = """You convert raw resume text into a strict JSON schema. Output ONLY valid JSON, no markdown fences, no commentary.

Schema:
{
  "name": string,
  "title": string,
  "location": string,
  "contact": {"email": string, "phone": string, "github": string, "linkedin": string},
  "summary": string,
  "education": [{"degree": string, "institution": string, "year": string, "cgpa": string (optional), "score": string (optional)}],
  "skills": {"languages": [string], "devops_tools": [string], "cloud": [string], "data_web": [string], "other": [string]},
  "projects": [{"name": string, "tech": [string], "description": string, "github": string or null, "collaborators": [string] (optional)}],
  "experience": [{"role": string, "company": string, "duration": string, "description": string}],
  "certifications": [string],
  "achievements": [string],
  "additional_info": [string]
}

Rules:
- Extract only what is present in the resume text. Leave arrays empty ([]) if no relevant data exists. Do not invent facts.
- Keep original wording where possible for descriptions.
"""

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

def load_candidate_data():
    with open(DATA_PATH) as f:
        return json.load(f)

CANDIDATE_DATA = load_candidate_data()

class Msg(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[Msg]   # <-- matches sahil-os-frontend's { messages: [...] }

def looks_like_job_description(text: str) -> bool:
    keywords = ["requirements", "responsibilities", "we are hiring", "we're hiring", "qualifications", "job description", "years of experience", "must have", "nice to have"]
    lower = text.lower()
    return len(text) > 200 and sum(1 for k in keywords if k in lower) >= 1

@app.post("/chat")
async def chat(req: ChatRequest):
    processed_messages = [{"role": m.role, "content": m.content} for m in req.messages]

    if processed_messages and processed_messages[-1]["role"] == "user":
        last_content = processed_messages[-1]["content"]
        if looks_like_job_description(last_content):
            print("=== JD DETECTED ===")
            processed_messages[-1]["content"] = (
                last_content
                + "\n\n(This is a job description. Your reply MUST start with a line in exactly this format: \"Suitability Score: XX%\" where XX is a real number you calculate based on how well the candidate data matches this JD. Do not skip this line or write \"Suitability:\" without a percentage.)"
            )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\nCandidate data:\n" + json.dumps(CANDIDATE_DATA)},
        *processed_messages,
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

@app.post("/upload-resume")
async def upload_resume(password: str = Form(...), file: UploadFile = File(...)):
    global CANDIDATE_DATA

    if password != UPLOAD_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password")

    raw_bytes = await file.read()

    if file.filename.lower().endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw_bytes))
        resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        resume_text = raw_bytes.decode("utf-8", errors="ignore")

    if not resume_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SCHEMA_INSTRUCTIONS},
            {"role": "user", "content": resume_text},
        ],
    )

    raw_json = completion.choices[0].message.content.strip()
    raw_json = raw_json.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="AI failed to produce valid JSON, try again")

    with open(DATA_PATH, "w") as f:
        json.dump(parsed, f, indent=2)

    CANDIDATE_DATA = parsed

    return {"status": "success", "message": "Resume updated", "name": parsed.get("name", "unknown")}