from fastapi import FastAPI, Query
import httpx
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# =========================
# ENV + AI CLIENT
# =========================
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ai_client = OpenAI(api_key=OPENAI_API_KEY)

REMOTEOK_API_URL = "https://remoteok.com/api"

BASE_DIR = os.path.dirname(__file__)
STATE_FILE = os.path.join(BASE_DIR, "job_state.json")

# =========================
# STATE HELPERS
# =========================
def load_state():
    if not os.path.exists(STATE_FILE):
        return {"saved": [], "applied": []}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

# =========================
# SCORING
# =========================
KEYWORDS = [
    "it support", "service desk", "helpdesk",
    "windows", "office 365", "o365",
    "active directory", "vpn",
    "citrix", "vmware", "azure",
    "sccm", "servicenow", "jira",
    "remote support", "ticketing"
]

def calculate_score(text: str) -> int:
    score = 0
    for kw in KEYWORDS:
        if kw in text:
            score += 8
    score += 20
    return min(score, 100)

# =========================
# APP FACTORY
# =========================
def create_app():
    app = FastAPI(title="JobBot API")

    # =====================
    # HEALTH
    # =====================
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # =====================
    # JOBS
    # =====================
    @app.get("/jobs")
    async def jobs(
        query: str = Query(default="IT Support"),
        limit: int = Query(default=20, ge=1, le=50),
    ):
        q = query.lower()
        results = []
        state = load_state()

        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(
                REMOTEOK_API_URL,
                headers={"User-Agent": "jobbot/1.0"}
            )
            r.raise_for_status()
            data = r.json()

        for item in data:
            if not isinstance(item, dict) or "id" not in item:
                continue

            title = (item.get("position") or item.get("title") or "").strip()
            description = (item.get("description") or "") or ""
            company = (item.get("company") or "").strip()
            url = item.get("url") or item.get("apply_url")
            tags = item.get("tags") or []

            combined = (title + " " + description + " " + " ".join(tags)).lower()
            if q not in combined:
                continue

            job_id = f"remoteok-{item.get('id')}"
            score = calculate_score(combined)

            results.append({
                "id": job_id,
                "title": title or "Unknown role",
                "company": company or None,
                "location": "Remote",
                "is_remote": True,
                "url": url,
                "source": "remoteok",
                "score": score,
                "description": description,
                "saved": job_id in state["saved"],
                "applied": job_id in state["applied"]
            })

            if len(results) >= limit:
                break

        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # =====================
    # SAVE / UNSAVE
    # =====================
    @app.post("/jobs/{job_id}/save")
    async def save_job(job_id: str):
        state = load_state()
        if job_id not in state["saved"]:
            state["saved"].append(job_id)
        save_state(state)
        return {"saved": True}

    @app.post("/jobs/{job_id}/unsave")
    async def unsave_job(job_id: str):
        state = load_state()
        if job_id in state["saved"]:
            state["saved"].remove(job_id)
        save_state(state)
        return {"saved": False}

    # =====================
    # APPLIED / UNDO
    # =====================
    @app.post("/jobs/{job_id}/applied")
    async def mark_applied(job_id: str):
        state = load_state()
        if job_id not in state["applied"]:
            state["applied"].append(job_id)
        save_state(state)
        return {"applied": True}

    @app.post("/jobs/{job_id}/undo-applied")
    async def undo_applied(job_id: str):
        state = load_state()
        if job_id in state["applied"]:
            state["applied"].remove(job_id)
        save_state(state)
        return {"applied": False}

    # =====================
    # LIST SAVED / APPLIED
    # =====================
    @app.get("/saved")
    async def get_saved():
        return load_state()["saved"]

    @app.get("/applied")
    async def get_applied():
        return load_state()["applied"]

    return app
