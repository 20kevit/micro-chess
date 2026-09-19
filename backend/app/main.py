"""FastAPI application. Routes only wire modules; logic lives in services."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.api import API_V1_PREFIX
from app.core.config import settings
from app.core.errors import register_error_handlers
from app.core.frontend import mount_spa_if_present
from app.core.logging import RequestIdMiddleware, configure_logging
from app.db.session import init_db
from app.modules.admin.router import router as admin_router
from app.modules.adaptive.router import coach_router as adaptive_coach_router
from app.modules.adaptive.router import me_router as adaptive_router
from app.modules.adaptive.router import parent_router as adaptive_parent_router
from app.modules.auth.router import router as auth_router
from app.modules.notifications.router import router as notifications_router
from app.modules.balance_scale.router import router as balance_scale_router
from app.modules.blindfold_calculation.router import router as blindfold_calculation_router
from app.modules.blindfold_square_vision.router import router as square_vision_router
from app.modules.captures.router import router as captures_router
from app.modules.chinese_board.router import router as chinese_board_router
from app.modules.exercises.router import router as exercises_router
from app.modules.get_out_of_check.router import router as get_out_of_check_router
from app.modules.give_check.router import router as give_check_router
from app.modules.legal_destinations.router import router as legal_destinations_router
from app.modules.material_comparison.router import router as heavier_side_router
from app.modules.pathfinding.router import router as pathfinding_router
from app.modules.pathfinding_obstacles.router import router as obstacle_pathfinding_router
from app.modules.piece_recognition.router import router as piece_recognition_router
from app.modules.player.router import router as player_router
from app.modules.relationships.router import coach_router as coach_router
from app.modules.relationships.router import own_router as relationships_own_router
from app.modules.relationships.router import parent_router as parent_router
from app.modules.relationships.router import router as relationships_router
from app.modules.support.router import router as support_router
from app.modules.progress.router import router as attempts_router
from app.modules.puzzles.router import router as puzzles_router
from app.modules.recommendations.router import router as recommendations_router
from app.modules.trapped_pieces.router import router as trapped_pieces_router
from app.modules.undefended_pieces.router import router as undefended_pieces_router
from app.modules.users.router import router as users_router

# Register exercise validators (no core-flow changes needed per exercise).
import app.modules.blindfold_square_vision as _blindfold_square_vision  # noqa: F401
import app.modules.blindfold_calculation as _blindfold_calculation  # noqa: F401
import app.modules.captures as _captures  # noqa: F401
import app.modules.chinese_board as _chinese_board  # noqa: F401
import app.modules.balance_scale as _balance_scale  # noqa: F401
import app.modules.checkmate as _checkmate  # noqa: F401
import app.modules.get_out_of_check as _get_out_of_check  # noqa: F401
import app.modules.give_check as _give_check  # noqa: F401
import app.modules.legal_destinations as _legal_destinations  # noqa: F401
import app.modules.material_comparison as _material_comparison  # noqa: F401
import app.modules.reverse_opening as _reverse_opening  # noqa: F401
import app.modules.opening_traps as _opening_traps  # noqa: F401
from app.modules.reverse_opening.router import router as reconstruction_router
import app.modules.pathfinding as _pathfinding  # noqa: F401
import app.modules.pathfinding_obstacles as _pathfinding_obstacles  # noqa: F401
import app.modules.piece_recognition as _piece_recognition  # noqa: F401
import app.modules.pin as _pin  # noqa: F401
import app.modules.trapped_pieces as _trapped_pieces  # noqa: F401
import app.modules.undefended_pieces as _undefended_pieces  # noqa: F401
# Castling Rights sits at the end of the exercise roadmap (see docs/EXERCISES.md).
import app.modules.castling_rights as _castling_rights  # noqa: F401


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(settings.log_level)
    settings.ensure_ready()
    init_db()
    yield


app = FastAPI(title="MicroChess", version="0.1.0", lifespan=lifespan)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Added last so it runs outermost: every response carries X-Request-ID.
app.add_middleware(RequestIdMiddleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth_router, prefix=API_V1_PREFIX)
app.include_router(admin_router, prefix=API_V1_PREFIX)
app.include_router(balance_scale_router, prefix=API_V1_PREFIX)
app.include_router(blindfold_calculation_router, prefix=API_V1_PREFIX)
app.include_router(square_vision_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(exercises_router, prefix=API_V1_PREFIX)
app.include_router(captures_router, prefix=API_V1_PREFIX)
app.include_router(chinese_board_router, prefix=API_V1_PREFIX)
app.include_router(get_out_of_check_router, prefix=API_V1_PREFIX)
app.include_router(give_check_router, prefix=API_V1_PREFIX)
app.include_router(pathfinding_router, prefix=API_V1_PREFIX)
app.include_router(obstacle_pathfinding_router, prefix=API_V1_PREFIX)
app.include_router(piece_recognition_router, prefix=API_V1_PREFIX)
app.include_router(player_router, prefix=API_V1_PREFIX)
app.include_router(support_router, prefix=API_V1_PREFIX)
app.include_router(notifications_router, prefix=API_V1_PREFIX)
app.include_router(adaptive_router, prefix=API_V1_PREFIX)
app.include_router(adaptive_coach_router, prefix=API_V1_PREFIX)
app.include_router(adaptive_parent_router, prefix=API_V1_PREFIX)
app.include_router(relationships_router, prefix=API_V1_PREFIX)
app.include_router(coach_router, prefix=API_V1_PREFIX)
app.include_router(parent_router, prefix=API_V1_PREFIX)
app.include_router(relationships_own_router, prefix=API_V1_PREFIX)
app.include_router(legal_destinations_router, prefix=API_V1_PREFIX)
app.include_router(heavier_side_router, prefix=API_V1_PREFIX)
app.include_router(reconstruction_router, prefix=API_V1_PREFIX)
app.include_router(puzzles_router, prefix=API_V1_PREFIX)
app.include_router(attempts_router, prefix=API_V1_PREFIX)
app.include_router(recommendations_router, prefix=API_V1_PREFIX)
app.include_router(trapped_pieces_router, prefix=API_V1_PREFIX)
app.include_router(undefended_pieces_router, prefix=API_V1_PREFIX)

# Last: serve the prebuilt frontend (Vite dist/ deployed as
# backend/static/) with SPA fallback. No-op when the bundle is absent
# (local development, where the Vite dev server owns the frontend), so
# API-only behavior is unchanged there.
mount_spa_if_present(app)
