"""FastAPI application. Routes only wire modules; logic lives in services."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db
from app.modules.auth.router import router as auth_router
from app.modules.exercises.router import router as exercises_router
from app.modules.progress.router import router as attempts_router
from app.modules.puzzles.router import router as puzzles_router
from app.modules.users.router import router as users_router

# Register exercise validators (no core-flow changes needed per exercise).
import app.modules.captures as _captures  # noqa: F401
import app.modules.legal_destinations as _legal_destinations  # noqa: F401
import app.modules.piece_recognition as _piece_recognition  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MicroChess", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(exercises_router, prefix="/api/v1")
app.include_router(puzzles_router, prefix="/api/v1")
app.include_router(attempts_router, prefix="/api/v1")
