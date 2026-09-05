"""Exercise 1 target categories: color + piece-kind set + Persian wording.

One clean representation instead of special-case branches: a category is a
``Category`` (key, color, kinds, Persian name, hint). The generator picks a
category uniformly and derives target squares from its definition; the
validator/scorer keep working on the resulting square set unchanged, so new
categories never touch grading.

Categories (16): 12 individual piece types (white/black x pawn/knight/
bishop/rook/queen/king) plus 4 groups — light pieces (knight+bishop) and
heavy pieces (rook+queen) in both colors.

Legacy ``TARGETS``/``CANONICAL_TARGETS`` in ``validator.py`` stay untouched
for backward compatibility with seeded puzzles and existing tests.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.piece_recognition.validator import CANONICAL_TARGETS

COLOR_FA: dict[str, str] = {"white": "سفید", "black": "سیاه"}

# Persian names per piece kind (python-chess lowercase symbols).
PIECE_FA: dict[str, tuple[str, str]] = {
    # kind: (singular, plural)
    "p": ("سرباز", "سربازهای"),
    "n": ("اسب", "اسب‌های"),
    "b": ("فیل", "فیل‌های"),
    "r": ("رخ", "رخ‌های"),
    "q": ("وزیر", "وزیرهای"),
    "k": ("شاه", "شاه"),
}

HINT_FA: dict[str, str] = {
    "p": "سربازها قدم‌به‌قدم جلو می‌روند؛ ردیف‌های جلو را نگاه کن.",
    "n": "اسب به شکل L می‌پرد؛ وسط و گوشه‌های صفحه را نگاه کن.",
    "b": "فیل فقط روی خانه‌های هم‌رنگ خودش حرکت می‌کند.",
    "r": "رخ‌ها معمولاً در ستون‌ها و ردیف‌های باز ایستاده‌اند.",
    "q": "وزیر قوی‌ترین مهره است؛ اطراف شاه و مرکز را نگاه کن.",
    "k": "شاه معمولاً پشت مهره‌های خودش پنهان شده است.",
}

GROUP_MINOR_HINT = "سوار سبک یعنی اسب و فیل؛ هر دو را پیدا کن."
GROUP_HEAVY_HINT = "سوار سنگین یعنی رخ و وزیر؛ هر دو را پیدا کن."


@dataclass(frozen=True)
class Category:
    """One askable question: color + included piece kinds + Persian wording."""

    key: str
    color: str  # "white" | "black"
    kinds: tuple[str, ...]
    # Persian noun phrase without color, e.g. "سربازهای", "سوارهای سبک".
    name_fa: str
    # Singular noun for explanations, e.g. "سرباز", "سوار سبک".
    singular_fa: str
    hint_fa: str
    # Kings read naturally in singular ("شاه سفید را پیدا کن").
    single: bool = False

    def target_spec(self) -> dict[str, object]:
        """Shape accepted by ``squares_for_target``."""
        return {"color": self.color, "kinds": list(self.kinds)}

    def prompt_fa(self) -> str:
        color = COLOR_FA[self.color]
        if self.single:
            return f"{self.name_fa} {color} را پیدا کن."
        return f"تمام {self.name_fa} {color} را پیدا کن."

    def explanation_fa(self, squares: list[str]) -> str:
        color = COLOR_FA[self.color]
        if not squares:
            return (
                f"در این وضعیت {self.singular_fa} {color} وجود ندارد؛ "
                "پاسخ درست این است که هیچ خانه‌ای انتخاب نکنی."
            )
        return f"{self.singular_fa} {color} در خانه‌های {'، '.join(squares)} است."


def _individual_categories() -> dict[str, Category]:
    out: dict[str, Category] = {}
    for key in sorted(CANONICAL_TARGETS):
        target = CANONICAL_TARGETS[key]
        kind = target["kinds"][0]
        singular, plural = PIECE_FA[kind]
        out[key] = Category(
            key=key,
            color=target["color"],
            kinds=(kind,),
            name_fa=singular if kind == "k" else plural,
            singular_fa=singular,
            hint_fa=HINT_FA[kind],
            single=(kind == "k"),
        )
    return out


CATEGORIES: dict[str, Category] = {
    **_individual_categories(),
    "white-minor": Category(
        key="white-minor",
        color="white",
        kinds=("n", "b"),
        name_fa="سوارهای سبک",
        singular_fa="سوار سبک",
        hint_fa=GROUP_MINOR_HINT,
    ),
    "black-minor": Category(
        key="black-minor",
        color="black",
        kinds=("n", "b"),
        name_fa="سوارهای سبک",
        singular_fa="سوار سبک",
        hint_fa=GROUP_MINOR_HINT,
    ),
    "white-heavy": Category(
        key="white-heavy",
        color="white",
        kinds=("r", "q"),
        name_fa="سوارهای سنگین",
        singular_fa="سوار سنگین",
        hint_fa=GROUP_HEAVY_HINT,
    ),
    "black-heavy": Category(
        key="black-heavy",
        color="black",
        kinds=("r", "q"),
        name_fa="سوارهای سنگین",
        singular_fa="سوار سنگین",
        hint_fa=GROUP_HEAVY_HINT,
    ),
}

# Uniform draw space: 12 individual + 4 group categories. Groups share the
# same probability mass per key, so they appear regularly (~25% combined)
# without dominating; zero-target questions stay possible for every key.
CATEGORY_KEYS: tuple[str, ...] = tuple(sorted(CATEGORIES))

GROUP_KEYS: tuple[str, ...] = ("black-heavy", "black-minor", "white-heavy", "white-minor")
