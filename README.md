# AI Portfolio Backend

FastAPI backend that powers an AI chat assistant representing me — it answers questions about my skills, projects, and experience using an LLM, based only on structured data I provide (no hallucination).

**Frontend repo:** https://github.com/sahilransing2004-netizen/ai-portfolio-frontend

## Features
- Streaming chat responses over a REST endpoint
- LLM answers grounded strictly in provided candidate data
- System prompt designed to avoid hallucination and stay professional
- Conversation history support (multi-turn context)

## Tech Stack
- FastAPI
- Python
- Groq API (LLM inference)

## Getting Started

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file with:
Run the server:
```bash
uvicorn main:app --reload
```

## API

`POST /chat`
Accepts a list of `{role, content}` messages and streams back the assistant's response.

## Project Structure
## Author
Sahil Ransing — B.Tech Electronics & Computer Engineering, MIT ADT University, Pune
[GitHub](https://github.com/sahilransing2004-netizen)
