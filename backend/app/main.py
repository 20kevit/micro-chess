"""FastAPI application. Routes only wire modules; logic lives in services."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.session import init_db
from app.modules.auth.router import router as auth_router
from app.modules.balance_scale.router import router as balance_scale_router
from app.modules.captures.router import router as captures_router
from app.modules.exercises.router import router as exercises_router
from app.modules.get_out_of_check.router import router as get_out_of_check_router
from app.modules.give_check.router import router as give_check_router
from app.modules.legal_destinations.router import router as legal_destinations_router
from app.modules.pathfinding.router import router as pathfinding_router
from app.modules.pathfinding_obstacles.router import router as obstacle_pathfinding_router
from app.modules.piece_recognition.router import router as piece_recognition_router
from app.modules.progress.router import router as attempts_router
from app.modules.puzzles.router import router as puzzles_router
from app.modules.undefended_pieces.router import router as undefended_pieces_router
from app.modules.users.router import router as users_router

# Register exercise validators (no core-flow changes needed per exercise).
import app.modules.blindfold_square_vision as _blindfold_square_vision  # noqa: F401
import app.modules.blindfold_calculation as _blindfold_calculation  # noqa: F401
import app.modules.captures as _captures  # noqa: F401
import app.modules.balance_scale as _balance_scale  # noqa: F401
import app.modules.checkmate as _checkmate  # noqa: F401
import app.modules.get_out_of_check as _get_out_of_check  # noqa: F401
import app.modules.give_check as _give_check  # noqa: F401
import app.modules.legal_destinations as _legal_destinations  # noqa: F401
import app.modules.material_comparison as _material_comparison  # noqa: F401
import app.modules.memory_board as _memory_board  # noqa: F401
import app.modules.opening_move_reconstruction as _opening_move_reconstruction  # noqa: F401
import app.modules.opening_traps as _opening_traps  # noqa: F401
from app.modules.opening_move_reconstruction.router import router as reconstruction_router
import app.modules.pathfinding as _pathfinding  # noqa: F401
import app.modules.pathfinding_obstacles as _pathfinding_obstacles  # noqa: F401
import app.modules.piece_recognition as _piece_recognition  # noqa: F401
import app.modules.pin as _pin  # noqa: F401
import app.modules.rule_of_the_square as _rule_of_the_square  # noqa: F401
import app.modules.trapped_pieces as _trapped_pieces  # noqa: F401
import app.modules.undefended_pieces as _undefended_pieces  # noqa: F401
# Castling Rights sits at the end of the exercise roadmap (see docs/EXERCISES.md).
import app.modules.castling_rights as _castling_rights  # noqa: F401


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
app.include_router(balance_scale_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(exercises_router, prefix="/api/v1")
app.include_router(captures_router, prefix="/api/v1")
app.include_router(get_out_of_check_router, prefix="/api/v1")
app.include_router(give_check_router, prefix="/api/v1")
app.include_router(pathfinding_router, prefix="/api/v1")
app.include_router(obstacle_pathfinding_router, prefix="/api/v1")
app.include_router(piece_recognition_router, prefix="/api/v1")
app.include_router(legal_destinations_router, prefix="/api/v1")
app.include_router(reconstruction_router, prefix="/api/v1")
app.include_router(puzzles_router, prefix="/api/v1")
app.include_router(attempts_router, prefix="/api/v1")
app.include_router(undefended_pieces_router, prefix="/api/v1")
