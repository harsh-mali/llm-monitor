from fastapi import FastAPI, Form, BackgroundTasks
from fastapi.responses import HTMLResponse
from groq import Groq
from supabase import create_client
from dotenv import load_dotenv
import os, time, asyncio, re
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
executor = ThreadPoolExecutor(max_workers=10)

app = FastAPI()

# ── QUALITY SCORING ──────────────────────────────────────

def score_length(text: str) -> float:
    l = len(text)
    if l < 50:   return 0.2
    if l < 200:  return 0.5
    if l < 500:  return 0.7
    if l < 1500: return 0.9
    return 1.0

def score_coherence(text: str) -> float:
    """Score based on sentence structure and formatting"""
    sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 10]
    if len(sentences) == 0: return 0.2
    if len(sentences) < 2:  return 0.5
    # Bonus for structured responses (lists, paragraphs)
    has_structure = bool(re.search(r'\n|•|\d+\.|##|\*\*', text))
    base = min(1.0, len(sentences) / 8)
    return min(1.0, base + (0.15 if has_structure else 0))

def score_relevance(prompt: str, response: str) -> float:
    """Check if key words from prompt appear in response"""
    prompt_words = set(w.lower() for w in prompt.split() if len(w) > 3)
    response_lower = response.lower()
    if not prompt_words: return 0.5
    matches = sum(1 for w in prompt_words if w in response_lower)
    return min(1.0, matches / max(len(prompt_words), 1))

def llm_judge(prompt: str, response: str) -> dict:
    """Use Groq to score the response — only called when score < 0.7"""
    judge_prompt = f"""Rate this AI response on a scale of 1-10.

PROMPT: {prompt[:200]}
RESPONSE: {response[:400]}

Reply with ONLY a JSON object like this:
{{"score": 7, "reason": "one sentence reason", "flag": false}}

flag should be true if the response is harmful, toxic, or inappropriate."""

    try:
        result = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": judge_prompt}],
            max_tokens=100
        )
        import json
        raw = result.choices[0].message.content.strip()
        # Extract JSON from response
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            return {
                "llm_score": round(data.get("score", 5) / 10, 2),
                "llm_reason": data.get("reason", ""),
                "flagged": data.get("flag", False)
            }
    except:
        pass
    return {"llm_score": None, "llm_reason": "", "flagged": False}

def compute_quality(prompt: str, response: str, use_llm_judge: bool = False) -> dict:
    """Full quality analysis"""
    l_score = score_length(response)
    c_score = score_coherence(response)
    r_score = score_relevance(prompt, response)
    combined = round((l_score * 0.3) + (c_score * 0.35) + (r_score * 0.35), 3)

    result = {
        "quality_score": combined,
        "length_score": l_score,
        "coherence_score": c_score,
        "relevance_score": r_score,
        "llm_score": None,
        "llm_reason": "",
        "flagged": False
    }

    # Call LLM judge only for low scores — saves quota
    if use_llm_judge and combined < 0.7:
        judge = llm_judge(prompt, response)
        result.update(judge)
        # Blend LLM score with computed score
        if judge["llm_score"]:
            result["quality_score"] = round((combined * 0.6) + (judge["llm_score"] * 0.4), 3)

    return result

# ── BACKGROUND LOGGING ───────────────────────────────────

def _log(data: dict):
    try:
        supabase.table("llm_logs").insert(data).execute()
    except Exception as e:
        print(f"Log error: {e}")

async def log_async(data: dict):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, _log, data)

# ── GROQ CALL (sync, runs in thread) ─────────────────────

def call_groq(prompt: str) -> tuple:
    start = time.time()
    response = groq_client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}]
    )
    latency = int((time.time() - start) * 1000)
    return response.choices[0].message.content, latency

async def call_groq_async(prompt: str) -> tuple:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, call_groq, prompt)

# ── ROUTES ───────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home():
    with open("index.html") as f:
        return f.read()

@app.post("/query")
async def query(prompt: str = Form(...), background_tasks: BackgroundTasks = None):
    """Single prompt — async logging so response is instant"""
    response_text, latency = await call_groq_async(prompt)
    quality = compute_quality(prompt, response_text, use_llm_judge=False)

    log_data = {
        "prompt": prompt,
        "response": response_text,
        "latency_ms": latency,
        "response_len": len(response_text),
        "quality_score": quality["quality_score"],
        "length_score": quality["length_score"],
        "coherence_score": quality["coherence_score"],
        "relevance_score": quality["relevance_score"],
        "flagged": quality["flagged"],
        "session_type": "single"
    }
    background_tasks.add_task(log_async, log_data)

    return {
        "response": response_text,
        "latency_ms": latency,
        "quality": quality
    }

@app.post("/batch")
async def batch(prompts: str = Form(...), background_tasks: BackgroundTasks = None):
    """Multiple prompts — run all concurrently, return all results"""
    prompt_list = [p.strip() for p in prompts.strip().split("\n") if p.strip()]
    if not prompt_list:
        return {"error": "No prompts provided"}
    if len(prompt_list) > 10:
        return {"error": "Max 10 prompts per batch"}

    # Run all prompts concurrently
    tasks = [call_groq_async(p) for p in prompt_list]
    results = await asyncio.gather(*tasks)

    output = []
    for prompt, (response_text, latency) in zip(prompt_list, results):
        quality = compute_quality(prompt, response_text, use_llm_judge=True)
        log_data = {
            "prompt": prompt,
            "response": response_text,
            "latency_ms": latency,
            "response_len": len(response_text),
            "quality_score": quality["quality_score"],
            "length_score": quality["length_score"],
            "coherence_score": quality["coherence_score"],
            "relevance_score": quality["relevance_score"],
            "flagged": quality["flagged"],
            "llm_score": quality["llm_score"],
            "llm_reason": quality["llm_reason"],
            "session_type": "batch"
        }
        background_tasks.add_task(log_async, log_data)
        output.append({
            "prompt": prompt,
            "response": response_text,
            "latency_ms": latency,
            "quality": quality
        })

    return {"results": output, "total": len(output)}

@app.post("/simulate")
async def simulate(prompt: str = Form(...), users: int = Form(5), background_tasks: BackgroundTasks = None):
    """Simulate N concurrent users sending the same prompt"""
    if users > 10: users = 10

    tasks = [call_groq_async(prompt) for _ in range(users)]
    results = await asyncio.gather(*tasks)

    latencies = []
    qualities = []
    output = []

    for i, (response_text, latency) in enumerate(results):
        quality = compute_quality(prompt, response_text)
        latencies.append(latency)
        qualities.append(quality["quality_score"])
        log_data = {
            "prompt": f"[SIM-USER-{i+1}] {prompt}",
            "response": response_text,
            "latency_ms": latency,
            "response_len": len(response_text),
            "quality_score": quality["quality_score"],
            "length_score": quality["length_score"],
            "coherence_score": quality["coherence_score"],
            "relevance_score": quality["relevance_score"],
            "flagged": quality["flagged"],
            "session_type": "simulation"
        }
        background_tasks.add_task(log_async, log_data)
        output.append({
            "user": i + 1,
            "latency_ms": latency,
            "quality_score": quality["quality_score"],
            "flagged": quality["flagged"]
        })

    return {
        "prompt": prompt,
        "users_simulated": users,
        "results": output,
        "summary": {
            "min_latency": min(latencies),
            "max_latency": max(latencies),
            "avg_latency": round(sum(latencies) / len(latencies)),
            "avg_quality": round(sum(qualities) / len(qualities), 3),
            "flagged_count": sum(1 for r in output if r["flagged"])
        }
    }

@app.get("/logs")
async def get_logs():
    result = supabase.table("llm_logs").select("*").order("created_at", desc=True).limit(100).execute()
    return result.data

@app.get("/stats")
async def get_stats():
    """Aggregated stats for dashboard"""
    result = supabase.table("llm_logs").select("*").execute()
    logs = result.data
    if not logs:
        return {}

    single = [l for l in logs if l.get("session_type") == "single"]
    batch  = [l for l in logs if l.get("session_type") == "batch"]
    sim    = [l for l in logs if l.get("session_type") == "simulation"]

    def avg(lst, key):
        vals = [l[key] for l in lst if l.get(key) is not None]
        return round(sum(vals) / len(vals), 3) if vals else 0

    return {
        "total_queries": len(logs),
        "single_count": len(single),
        "batch_count": len(batch),
        "sim_count": len(sim),
        "avg_latency": avg(logs, "latency_ms"),
        "avg_quality": avg(logs, "quality_score"),
        "avg_length_score": avg(logs, "length_score"),
        "avg_coherence_score": avg(logs, "coherence_score"),
        "avg_relevance_score": avg(logs, "relevance_score"),
        "flagged_count": sum(1 for l in logs if l.get("flagged")),
    }