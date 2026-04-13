# LLM Monitoring Pipeline

> A production-style MLOps observability tool for monitoring LLM performance in real time.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=flat-square&logo=supabase&logoColor=white)
![Groq](https://img.shields.io/badge/Groq-LLaMA_3.1-F55036?style=flat-square)

---

## What is this?

Most developers call an LLM API, get a response, and have no idea if it was fast, accurate, or consistent. This project solves that by building the **observability layer** that production AI systems need.

Every prompt sent through this tool is:
- Routed to **Groq's LLaMA 3.1** inference engine
- Scored for response quality (0.0 → 1.0)
- Logged to a **Supabase PostgreSQL** database with latency and metadata
- Displayed on a **live dashboard** with metrics and quality trends over time

This is not a chatbot. This is the infrastructure that monitors chatbots.

---

## Architecture

```
User Prompt
    │
    ▼
FastAPI Backend (/query)
    │
    ├──► Groq API (LLaMA 3.1-8b-instant)
    │         └── Response + Latency
    │
    ├──► Quality Scorer
    │         └── Score: 0.3 / 0.6 / 0.9 / 1.0
    │
    └──► Supabase (PostgreSQL)
              └── Logs: prompt, response, latency_ms, quality_score
                            │
                            ▼
                    Dashboard (/logs)
                    Live Metrics + Chart
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | Python, FastAPI |
| LLM Inference | Groq API (LLaMA 3.1 8B Instant) |
| Database | Supabase (PostgreSQL) |
| Frontend | HTML, JavaScript, Chart.js |
| Auth/Secrets | python-dotenv |

---

## Features

- **Real-time query interface** — send prompts and see responses instantly
- **Automatic quality scoring** — every response rated Poor / Okay / Good / Excellent
- **Latency tracking** — measures response time in milliseconds for every query
- **Live metrics dashboard** — total queries, average latency, average quality score
- **Quality trend chart** — visualise how response quality changes over time
- **Persistent logging** — all queries stored in PostgreSQL via Supabase
- **Responsive split-panel UI** — query panel left, metrics panel right

---

## Setup & Run

### 1. Clone the repo
```bash
git clone https://github.com/harsh-mali/llm-monitor.git
cd llm-monitor
```

### 2. Create virtual environment
```bash
py -3.12 -m venv venv
venv\Scripts\activate      # Windows
source venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up Supabase
- Create a project at [supabase.com](https://supabase.com)
- Run this SQL in the Supabase SQL Editor:

```sql
CREATE TABLE llm_logs (
    id            BIGSERIAL PRIMARY KEY,
    created_at    TIMESTAMP DEFAULT NOW(),
    prompt        TEXT NOT NULL,
    response      TEXT NOT NULL,
    model         TEXT DEFAULT 'llama-3.1-8b-instant',
    latency_ms    INTEGER,
    response_len  INTEGER,
    quality_score FLOAT
);

ALTER TABLE llm_logs DISABLE ROW LEVEL SECURITY;
```

### 5. Create `.env` file
```env
GROQ_API_KEY=your_groq_api_key_here
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
```

Get your Groq API key free at [console.groq.com](https://console.groq.com)

### 6. Run the app
```bash
uvicorn main:app --reload
```

Open [http://localhost:8000](http://localhost:8000)

---

## Quality Scoring Logic

Responses are scored based on length as a proxy for detail and completeness:

| Score | Label | Criteria |
|-------|-------|----------|
| 0.3 | Poor | Response under 50 characters |
| 0.6 | Okay | Response 50–200 characters |
| 0.9 | Good | Response 200–1000 characters |
| 1.0 | Excellent | Response over 1000 characters |

> **Note:** Length-based scoring is a baseline implementation. Future versions will use semantic similarity and embedding-based evaluation for more accurate quality assessment.

---

## Project Structure

```
llm-monitor/
├── main.py          # FastAPI backend — routes, Groq integration, Supabase logging
├── index.html       # Frontend dashboard — query interface + live metrics
├── .env             # Secret keys (never committed)
├── .gitignore       # Excludes .env, venv, __pycache__
├── requirements.txt # Python dependencies
└── README.md
```

---

## Future Improvements

- [ ] Semantic quality scoring using embeddings (cosine similarity)
- [ ] Alert system when quality drops below configurable threshold
- [ ] Support for multiple LLM providers (OpenAI, Anthropic, Gemini)
- [ ] Docker containerisation for one-command deployment
- [ ] Export logs to CSV for offline analysis
- [ ] Per-model performance comparison dashboard

---

## Why I Built This

In production AI systems, you don't just call an LLM — you monitor it. This project implements the observability layer that real MLOps engineers build at companies like Zensar, where I work on data pipelines for NVIDIA's Project GR00T humanoid foundation model. The patterns here — logging, scoring, dashboarding — directly mirror what production ML infrastructure teams do at scale.

---

## Author

**Harsh Mali** — MLOps & Data Infrastructure Engineer  
[LinkedIn](https://www.linkedin.com/in/harsh-mali-4448692b6/) | [GitHub](https://github.com/harsh-mali)
