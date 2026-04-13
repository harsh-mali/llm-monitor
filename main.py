from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from groq import Groq
from supabase import create_client
from dotenv import load_dotenv
import os, time

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

app = FastAPI()

def score_response(response_text: str) -> float:
    length = len(response_text)
    if length < 50:   return 0.3
    if length < 200:  return 0.6
    if length < 1000: return 0.9
    return 1.0

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html") as f:
        return f.read()

@app.post("/query")
async def query_gemini(prompt: str = Form(...)):
    start = time.time()
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    latency = int((time.time() - start) * 1000)
    response_text = response.choices[0].message.content
    quality = score_response(response_text)
    supabase.table("llm_logs").insert({
        "prompt": prompt,
        "response": response_text,
        "latency_ms": latency,
        "response_len": len(response_text),
        "quality_score": quality
    }).execute()
    return {"response": response_text, "latency_ms": latency, "quality_score": quality}

@app.get("/logs")
async def get_logs():
    result = supabase.table("llm_logs").select("*").order("created_at", desc=True).limit(50).execute()
    return result.data