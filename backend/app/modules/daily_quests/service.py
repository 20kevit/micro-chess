"""Daily quest service (P11).

Selection reuses recommendation/adaptive/skill infrastructure: no
parallel recommendation engine. Core = top recommendation; review =
exercise with recent failures/weak signal (adaptive overview) or second
recommendation pass; challenge = slightly harder/different exercise.

Stability: ``get_today`` creates the day once (unique constraint) and
returns the same rows on every refresh. Completion derives progress
from authoritative attempts (server counts), is idempotent, and grants
a one-time quest XP bonus reusing the existing XpEvent table (no second
gamification system).
"""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.adaptive import service as adaptive_service
from app.modules.daily_quests.models import (
    KIND_CHALLENGE,
    KIND_CORE,
    KIND_REVIEW,
    STATUS_COMPLETED,
    STATUS_PENDING,
    STATUS_STARTED,
    DailyQuest,
    DailyQuestDay,
)
from app.modules.onboarding.models import OnboardingProfile
from app.modules.progress.models import Attempt
from app.modules.recommendations import service as rec_service

# Informational quest value (≈ this much attempt XP is earned while
# filling a quest). No separate ledger write: attempts already earn XP
# through the existing gamification engine.
QUEST_BONUS_XP = 15


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_timezone(db: Session, user_id: int) -> str:
    row = db.query(OnboardingProfile).filter(OnboardingProfile.user_id == user_id).first()
    tz = (row.timezone if row else "") or "Asia/Tehran"
    try:
        ZoneInfo(tz)
    except Exception:
        tz = "Asia/Tehran"
    return tz


def local_today(tz_name: str, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        local = now.astimezone(ZoneInfo(tz_name))
    except Exception:
        local = now.astimezone(ZoneInfo("Asia/Tehran"))
    return local.strftime("%Y-%m-%d")


def _intensity_target(db: Session, user_id: int) -> int:
    row = db.query(OnboardingProfile).filter(OnboardingProfile.user_id == user_id).first()
    inten = (row.intensity if row else "standard") or "standard"
    return {"light": 3, "standard": 5, "intensive": 8}.get(inten, 5)


def _pick_exercises(db: Session, user_id: int) -> list[tuple[str, str, int | None]]:
    """(exercise_slug, kind_label_reason, puzzle_id) for the 3 slots."""
    core = rec_service.recommend_for_user(db, user_id)
    core_slug = core.exercise_slug if core else None
    core_puzzle = core.puzzle_id if core else None
    # Review: strongest remediation signal from adaptive overview.
    review_slug: str | None = None
    try:
        overview = adaptive_service.overview(db, user_id)
        for sig in overview.get("exercises", []):
            if sig.exercise == core_slug:
                continue
            if sig.reason in ("RECENT_FAILURES", "WEAK_EXERCISE", "MASTERY_REVIEW", "LOW_RECENT_ACTIVITY"):
                review_slug = sig.exercise
                break
    except Exception:
        review_slug = None
    # Challenge: next distinct recommendation-ish pick = adaptive top
    # differing from core/review, else deterministic second exercise.
    challenge_slug: str | None = None
    try:
        overview = adaptive_service.overview(db, user_id)
        for sig in overview.get("exercises", []):
            if sig.exercise in (core_slug, review_slug):
                continue
            if sig.reason in ("READY_FOR_HARDER", "APPROPRIATE_DIFFICULTY", "COLD_START"):
                challenge_slug = sig.exercise
                break
        if challenge_slug is None:
            for sig in overview.get("exercises", []):
                if sig.exercise not in (core_slug, review_slug):
                    challenge_slug = sig.exercise
                    break
    except Exception:
        challenge_slug = None
    slugs = [s for s in (core_slug, review_slug, challenge_slug) if s]
    # Fill from recommendation-ranked servable exercises if short.
    if len(slugs) < 3:
        try:
            state_slugs = sorted({s for (s,) in db.query(Attempt.exercise_slug).all()})
        except Exception:
            state_slugs = []
        from app.modules.puzzles.models import Puzzle

        known = sorted({s for (s,) in db.query(Puzzle.exercise_slug).all()})
        for s in known + state_slugs:
            if s not in slugs and len(slugs) < 3:
                if rec_service.eligible_puzzles(db, s):
                    slugs.append(s)
            if len(slugs) >= 3:
                break
    while len(slugs) < 3 and core_slug:
        slugs.append(core_slug)  # last resort: repeat core exercise, distinct puzzle
        if len(slugs) >= 3:
            break
    if not slugs:
        return []
    out: list[tuple[str, str, int | None]] = []
    kinds = (KIND_CORE, KIND_REVIEW, KIND_CHALLENGE)
    for i, slug in enumerate(slugs[:3]):
        puzzle_id = core_puzzle if i == 0 else None
        if puzzle_id is None:
            ability, _ = rec_service.ability_for(db, user_id, slug)
            cands = rec_service.eligible_puzzles(db, slug)
            if cands:
                best = min(cands, key=lambda p: (abs((p.initial_rating or 0) - ability), p.id or 0))
                puzzle_id = best.id
        out.append((slug, kinds[i], puzzle_id))
    return out


_TITLES = {
    KIND_CORE: ("تمرین اصلی", "روی مهارتی کار کن که الان بیشتر به کارت می‌آید."),
    KIND_REVIEW: ("مرور", "اشتباه‌های قبلی را مرور کن تا ماندگار شود."),
    KIND_CHALLENGE: ("چالش", "یک قدم جلوتر؛ کمی سخت‌تر و متنوع‌تر."),
}


def get_today(db: Session, user_id: int, *, tz_name: str | None = None) -> dict:
    tz = tz_name or _user_timezone(db, user_id)
    try:
        ZoneInfo(tz)
    except Exception:
        tz = "Asia/Tehran"
    day = local_today(tz)
    existing = (
        db.query(DailyQuestDay)
        .filter(DailyQuestDay.user_id == user_id, DailyQuestDay.local_date == day)
        .first()
    )
    if existing is None:
        existing = DailyQuestDay(user_id=user_id, local_date=day, timezone=tz)
        db.add(existing)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = (
                db.query(DailyQuestDay)
                .filter(DailyQuestDay.user_id == user_id, DailyQuestDay.local_date == day)
                .first()
            )
        db.refresh(existing)
        picks = _pick_exercises(db, user_id)
        target = _intensity_target(db, user_id)
        for slot, (slug, kind, puzzle_id) in enumerate(picks, start=1):
            title, desc = _TITLES[kind]
            db.add(
                DailyQuest(
                    day_id=existing.id, user_id=user_id, slot=slot, kind=kind,
                    title=title, description=desc, exercise_slug=slug,
                    puzzle_id=puzzle_id, target_count=target,
                )
            )
        try:
            db.commit()
        except IntegrityError:
            db.rollback()  # concurrent creator won; fall through to read
    quests = (
        db.query(DailyQuest)
        .filter(DailyQuest.day_id == existing.id)
        .order_by(DailyQuest.slot)
        .all()
    )
    for q in quests:
        q.progress = _progress_for(db, user_id, existing, q)
    db.commit()
    return {"day": existing, "quests": quests}


def _day_start_utc(day_row: DailyQuestDay) -> datetime:
    try:
        local_midnight = datetime.strptime(day_row.local_date, "%Y-%m-%d").replace(
            tzinfo=ZoneInfo(day_row.timezone or "Asia/Tehran")
        )
    except Exception:
        local_midnight = datetime.strptime(day_row.local_date, "%Y-%m-%d").replace(
            tzinfo=ZoneInfo("Asia/Tehran")
        )
    return local_midnight.astimezone(timezone.utc).replace(tzinfo=None)


def _progress_for(db: Session, user_id: int, day: DailyQuestDay, quest: DailyQuest) -> int:
    start = _day_start_utc(day)
    count = (
        db.query(Attempt)
        .filter(
            Attempt.user_id == user_id,
            Attempt.exercise_slug == quest.exercise_slug,
            Attempt.created_at >= start,
            Attempt.result.in_(("correct", "partial", "wrong")),
        )
        .count()
    )
    return min(count, quest.target_count or 1)


def start_quest(db: Session, user_id: int, quest_id: int) -> DailyQuest:
    quest = db.get(DailyQuest, quest_id)
    if quest is None or quest.user_id != user_id:
        raise ValueError("quest_not_found")
    if quest.status == STATUS_PENDING:
        quest.status = STATUS_STARTED
        quest.started_at = _utcnow()
        db.commit()
        db.refresh(quest)
    return quest


def complete_quest(db: Session, user_id: int, quest_id: int) -> DailyQuest:
    """Idempotent completion: progress must reach target; bonus XP once."""
    quest = db.get(DailyQuest, quest_id)
    if quest is None or quest.user_id != user_id:
        raise ValueError("quest_not_found")
    if quest.status == STATUS_COMPLETED:
        return quest  # idempotent replay
    day = db.get(DailyQuestDay, quest.day_id)
    progress = _progress_for(db, user_id, day, quest)
    quest.progress = progress
    if progress < (quest.target_count or 1):
        db.commit()
        raise ValueError("quest_incomplete")
    quest.status = STATUS_COMPLETED
    quest.completed_at = _utcnow()
    if not quest.reward_granted:
        # Reward reuses the existing gamification system: the attempts
        # that filled this quest already earned XP/streak/achievements
        # through progress.service.submit_attempt. No second ledger is
        # written here (XpEvent rows are per-attempt unique); this flag
        # only marks the one-time completion notification below.
        quest.reward_granted = True
        # Best-effort quest-completed notification (in-app only here;
        # fan-out to opted channels happens in notify service).
        try:
            from app.modules.notifications import service as notif_service

            notif_service.emit_event(
                db, user_id=user_id, type="journey.quest_completed",
                title="مأموریت کامل شد",
                body=f"{quest.title} کامل شد.",
                dedup_key=f"quest:{quest.id}:completed",
            )
        except Exception:
            pass
    db.commit()
    db.refresh(quest)
    return quest


def quest_view(day: DailyQuestDay, quest: DailyQuest) -> dict:
    return {
        "id": quest.id,
        "slot": quest.slot,
        "kind": quest.kind,
        "title": quest.title,
        "description": quest.description,
        "exercise_slug": quest.exercise_slug,
        "puzzle_id": quest.puzzle_id,
        "target_count": quest.target_count,
        "progress": quest.progress,
        "status": quest.status,
        "started_at": quest.started_at,
        "completed_at": quest.completed_at,
        "local_date": day.local_date,
    }
