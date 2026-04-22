# LLM Monitoring Pipeline

> A production-style MLOps observability platform for monitoring LLM performance — with multi-mode querying, multi-dimensional quality scoring, and a live analytics dashboard.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?style=flat-square&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat-square&logo=supabase&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.1-F55036?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)

---

## What is this?

Most developers call an LLM API and move on — they have zero visibility into whether the model is fast, accurate, or consistent. This project builds the **observability layer** that production AI systems need.

Every prompt is automatically:
- Routed to **Groq's LLaMA 3.1 8B** for inference
- Scored across **three quality dimensions** (length, coherence, relevance)
- Evaluated by an **LLM judge** when quality drops below threshold
- Logged asynchronously to **Supabase PostgreSQL** without blocking the response
- Reflected on a **live dashboard** with metric cards, trend charts, and filterable logs

---

## Three Operating Modes

| Mode | What it does | Key feature |
|------|-------------|-------------|
| **Single** | Send one prompt, get scored response | Full quality breakdown with 4 score bars |
| **Batch** | Paste up to 10 prompts, run all at once | `asyncio.gather()` concurrent execution |
| **Simulate** | Fire N concurrent users at the same prompt | Latency variance + per-user quality scoring |

---

## Architecture

```
THREE ENTRY POINTS:
  POST /query    → single prompt    → background logging (non-blocking)
  POST /batch    → N prompts        → asyncio.gather() concurrent execution
  POST /simulate → 1 prompt × N    → concurrent user load simulation

FLOW (all three modes):
  Input prompt(s)
       │
       ▼
  ThreadPoolExecutor → call_groq_async()   [Groq API — LLaMA 3.1 8B]
       │
       ▼
  compute_quality()
       ├── score_length()     [tiered: 0.2 / 0.5 / 0.7 / 0.9 / 1.0]
       ├── score_coherence()  [sentence count + structure bonus]
       ├── score_relevance()  [keyword overlap: prompt ↔ response]
       └── llm_judge()        [only when combined score < 0.7]
       │
       ▼
  BackgroundTasks.add_task() → Supabase insert  [non-blocking]
       │
       ▼
  Return response + quality scores instantly

DASHBOARD:
  GET /stats → aggregated metrics (total, per-mode, avg scores, flagged count)
  GET /logs  → last 100 rows, filterable by session_type
  Charts: quality over time + relevance overlay + latency bar chart
```

---

## Quality Scoring Engine

| Dimension | Weight | Method |
|-----------|--------|--------|
| **Length** | 30% | Tiered scoring based on character count — proxy for response detail |
| **Coherence** | 35% | Sentence count + bonus for structured responses (bullets, headers) |
| **Relevance** | 35% | Keyword overlap between prompt and response |
| **LLM Judge** | Blended | Groq scores the response 1–10 when combined score < 0.7. Blended 60/40. |

**Quality labels:** Poor (< 0.5) · Okay (0.5–0.7) · Good (0.7–0.9) · Excellent (≥ 0.9)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python 3.12, FastAPI |
| Concurrency | asyncio, ThreadPoolExecutor, BackgroundTasks |
| LLM Inference | Groq API (LLaMA 3.1 8B Instant) |
| LLM Evaluation | Groq LLM-as-Judge pattern |
| Database | Supabase (PostgreSQL) |
| Frontend | HTML, JavaScript, Chart.js |
| Secrets | python-dotenv |

---

## Setup & Run

### 1. Clone the repo
```bash
git clone https://github.com/your-username/llm-monitor.git
cd llm-monitor
```

### 2. Create virtual environment (Python 3.12)
```bash
py -3.12 -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up Supabase database

Create a project at [supabase.com](https://supabase.com), then run this in the SQL Editor:

```sql
CREATE TABLE llm_logs (
    id              BIGSERIAL PRIMARY KEY,
    created_at      TIMESTAMP DEFAULT NOW(),
    prompt          TEXT NOT NULL,
    response        TEXT NOT NULL,
    model           TEXT DEFAULT 'llama-3.1-8b-instant',
    latency_ms      INTEGER,
    response_len    INTEGER,
    quality_score   FLOAT,
    length_score    FLOAT,
    coherence_score FLOAT,
    relevance_score FLOAT,
    llm_score       FLOAT,
    llm_reason      TEXT,
    flagged         BOOLEAN DEFAULT FALSE,
    session_type    TEXT DEFAULT 'single'
);

ALTER TABLE llm_logs DISABLE ROW LEVEL SECURITY;
```

### 5. Create `.env` file
```env
GROQ_API_KEY=your_groq_api_key_here
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

Get your free Groq API key at [console.groq.com](https://console.groq.com)

### 6. Run
```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Dashboard UI |
| `POST` | `/query` | Single prompt — returns response + quality scores |
| `POST` | `/batch` | Multiple prompts (newline separated, max 10) — concurrent |
| `POST` | `/simulate` | Simulate N concurrent users on one prompt |
| `GET` | `/logs` | Last 100 log entries |
| `GET` | `/stats` | Aggregated metrics for dashboard |

---

## Project Structure

```
llm-monitor/
├── main.py          # FastAPI backend — all routes, scoring engine, concurrency logic
├── index.html       # Frontend — tabbed UI with single/batch/simulate modes
├── .env             # Secret keys (never committed)
├── .gitignore       # Excludes .env, venv, __pycache__
├── requirements.txt # Python dependencies
└── README.md
```

---

## Key Engineering Decisions

**Why `asyncio.gather()` for batch/simulate?**
Sequential calls would take N × latency time. Concurrent calls take ~1 × latency regardless of N. For 5 prompts at 1.3s each: sequential = 6.5s, concurrent = ~1.3s.

**Why `ThreadPoolExecutor` for Groq calls?**
Groq's Python SDK is synchronous (blocking). Running it directly in an async route would freeze the entire FastAPI event loop. Wrapping it in `run_in_executor()` runs it in a thread pool while keeping the event loop free.

**Why `BackgroundTasks` for logging?**
Database writes should never slow down the user-facing response. BackgroundTasks sends the HTTP response first, then runs the Supabase insert — decoupling user latency from database write latency.

**Why LLM judge only below 0.7?**
Selective evaluation conserves API quota and adds signal where it matters most. An obviously excellent response doesn't need a second opinion. A borderline response does.

---

## Future Improvements

- [ ] Embedding-based semantic relevance scoring (sentence-transformers)
- [ ] Quality alert system — webhook/notification when score drops below threshold
- [ ] Multi-model comparison mode — same prompt to multiple providers side-by-side
- [ ] Docker + docker-compose for one-command deployment
- [ ] Streaming response support for lower perceived latency
- [ ] Prompt template library with per-template quality tracking
- [ ] Export logs to CSV for offline analysis

---