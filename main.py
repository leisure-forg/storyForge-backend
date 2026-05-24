import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from dotenv import load_dotenv

from game.models import CreateGameResponse, GameConfig, PlayerAction, CustomTheme
from game.engine import GameEngine

load_dotenv()

BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

app = FastAPI(title="AI Story Adventure", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = GameEngine()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/game/new", response_model=CreateGameResponse)
async def new_game(config: GameConfig):
    if config.genre == "custom" and not config.custom_theme:
        raise HTTPException(status_code=400, detail="Custom genre requires custom_theme")
    game_id, segments = engine.create_game(config)
    intro = json.dumps([s.model_dump() for s in segments])
    return CreateGameResponse(game_id=game_id, intro=intro)


class ThemeGenerateRequest(BaseModel):
    hint: str = ""


@app.post("/api/theme/generate", response_model=CustomTheme)
async def generate_theme(req: ThemeGenerateRequest):
    try:
        theme = await engine.generate_theme(req.hint)
        return theme
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/game/{game_id}")
async def get_game(game_id: str):
    game = engine.games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")

    world_state = engine.world_manager.to_dict(game_id)
    return {
        "game_id": game_id,
        "config": game["config"].model_dump() if hasattr(game["config"], "model_dump") else game["config"],
        "world_state": world_state,
        "history_count": len(game["history"]),
    }


@app.post("/api/game/{game_id}/act")
async def act(game_id: str, action: PlayerAction):
    if game_id not in engine.games:
        raise HTTPException(status_code=404, detail="Game not found")

    return EventSourceResponse(
        engine.process_action(game_id, action.action)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=BACKEND_HOST, port=BACKEND_PORT)
