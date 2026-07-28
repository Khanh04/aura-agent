from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic_ai.messages import ModelMessagesTypeAdapter
from pydantic_core import to_jsonable_python

from app.agent.aura_agent import aura_agent
from app.schemas import ChatRequest, ChatResponse

app = FastAPI(title="Aura Lunar Almanac Chat Agent")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    history = ModelMessagesTypeAdapter.validate_python(req.history) if req.history else None
    prompt = f"(Hôm nay là {date.today().isoformat()}.)\n{req.message}"

    try:
        result = await aura_agent.run(prompt, message_history=history)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return ChatResponse(
        reply=result.output.message,
        lunar=result.output.lunar,
        history=to_jsonable_python(result.all_messages()),
    )


# Same-origin SPA, mirrors argus-agent's main.py -- skipped in dev if not built yet.
_frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if _frontend_dist.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
