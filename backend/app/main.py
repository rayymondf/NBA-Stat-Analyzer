import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from .routers import games, league, players  # noqa: E402

app = FastAPI(title="NBA Stat Analyzer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(players.router)
app.include_router(games.router)
app.include_router(league.router)

try:
    from .routers import ai  # noqa: E402
    app.include_router(ai.router)
except ImportError:
    pass

# Serve the built frontend when it exists (single-process "app mode")
DIST = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..",
                                    "frontend", "dist"))
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")),
              name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = os.path.join(DIST, path)
        if path and os.path.isfile(file):
            return FileResponse(file)
        return FileResponse(os.path.join(DIST, "index.html"))
