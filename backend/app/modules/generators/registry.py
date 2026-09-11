"""Central generator registry (Phase 07).

Each entry maps a stable generator code to its target exercise,
version, supported configuration, and a pure candidate builder.
Adding a generator means registering one entry here with its own
adapter — never editing unrelated generator implementations and
never branching core flow on exercise slugs.

Adapters reuse the exercise's own pure question builders
(``generate_question_data``); the exercise's content invariants
(``content.py``) independently re-verify every candidate during
the job, so generation and validation stay decoupled.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class GeneratorDefinition:
    code: str
    exercise_slug: str
    version: str
    description: str
    # Whitelisted configuration keys this generator accepts.
    allowed_config_keys: tuple[str, ...] = ()
    # JSON-schema-ish description exposed to admins (informational only;
    # the service enforces allowed_config_keys server-side).
    config_schema: dict[str, Any] = field(default_factory=dict)

    def build_candidate(self, rng: random.Random, config: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class _PieceRecognitionGenerator(GeneratorDefinition):
    code: str = "piece-recognition-v1"
    exercise_slug: str = "piece-recognition"
    version: str = "1.0.0"
    description: str = "Random position with a random piece target."
    allowed_config_keys: tuple[str, ...] = ()
    config_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})

    def build_candidate(self, rng: random.Random, config: dict[str, Any]) -> dict[str, Any]:
        from app.modules.piece_recognition import generator as gen

        data = gen.generate_question_data(rng)
        return {
            "fen": data["fen"],
            "position_json": {"target": data["target"]},
            "answer_json": {"squares": data["squares"], "target": data["target"]},
            "hint_json": data["hint_json"],
            "prompt_fa": data["prompt_fa"],
            "explanation": data["explanation"],
            "initial_rating": 900.0,
        }


@dataclass(frozen=True)
class _CapturesGenerator(GeneratorDefinition):
    code: str = "captures-v1"
    exercise_slug: str = "captures"
    version: str = "1.0.0"
    description: str = "One white hunter piece against black pieces."
    allowed_config_keys: tuple[str, ...] = ("piece_type",)
    config_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {"piece_type": {"type": "string", "enum": ["p", "n", "b", "r", "q"]}},
        }
    )

    def build_candidate(self, rng: random.Random, config: dict[str, Any]) -> dict[str, Any]:
        from app.modules.captures import generator as gen

        data = gen.generate_question_data(rng, piece_type=config.get("piece_type"))
        return {
            "fen": data["fen"],
            "position_json": {"from": data["from"], "profile": data["profile"]},
            "answer_json": {
                "squares": data["squares"],
                "from": data["from"],
                "profile": data["profile"],
            },
            "hint_json": data["hint_json"],
            "prompt_fa": data["prompt_fa"],
            "explanation": data["explanation"],
            "initial_rating": 900.0,
        }


@dataclass(frozen=True)
class _LegalDestinationsGenerator(GeneratorDefinition):
    code: str = "legal-destinations-v1"
    exercise_slug: str = "legal-destinations"
    version: str = "1.0.0"
    description: str = "White-only position with deliberate movement blockers."
    allowed_config_keys: tuple[str, ...] = ("piece_type",)
    config_schema: dict[str, Any] = field(
        default_factory=lambda: {
            "type": "object",
            "properties": {
                "piece_type": {"type": "string", "enum": ["p", "n", "b", "r", "q", "k"]}
            },
        }
    )

    def build_candidate(self, rng: random.Random, config: dict[str, Any]) -> dict[str, Any]:
        from app.modules.legal_destinations import generator as gen

        data = gen.generate_question_data(rng, piece_type=config.get("piece_type"))
        return {
            "fen": data["fen"],
            "position_json": {"from": data["from"], "profile": data["profile"]},
            "answer_json": {
                "squares": data["squares"],
                "from": data["from"],
                "profile": data["profile"],
            },
            "hint_json": data["hint_json"],
            "prompt_fa": data["prompt_fa"],
            "explanation": data["explanation"],
            "initial_rating": 900.0,
        }


_REGISTRY: dict[str, GeneratorDefinition] = {}


def _register(definition: GeneratorDefinition) -> None:
    _REGISTRY[definition.code] = definition


_register(_PieceRecognitionGenerator())
_register(_CapturesGenerator())
_register(_LegalDestinationsGenerator())


def get_generator(code: str) -> GeneratorDefinition | None:
    return _REGISTRY.get(code)


def available_generators() -> list[GeneratorDefinition]:
    return sorted(_REGISTRY.values(), key=lambda definition: definition.code)


def registered_generator_codes() -> list[str]:
    return sorted(_REGISTRY)
