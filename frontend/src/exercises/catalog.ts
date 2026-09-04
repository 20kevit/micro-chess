import type { FaKey } from "../i18n/fa";

// Central exercise catalog: every exercise has one entry with its slug,
// translation keys, availability status, and route (when playable).
// Pages render from status — never from per-slug conditionals — so adding
// Exercise 2 means appending one entry here, not touching components.

export type ExerciseStatus = "active" | "coming_soon";

export interface ExerciseMeta {
  slug: string;
  titleKey: FaKey;
  descKey: FaKey;
  status: ExerciseStatus;
  /** Playable route. Null while coming soon (card renders without a link). */
  route: string | null;
}

export const EXERCISE_CATALOG: ExerciseMeta[] = [
  { slug: "piece-recognition", titleKey: "exercises.piece-recognition.title", descKey: "exercises.piece-recognition.desc", status: "active", route: "/exercises/piece-recognition" },
  { slug: "legal-destinations", titleKey: "exercises.legal-destinations.title", descKey: "exercises.legal-destinations.desc", status: "active", route: "/exercises/legal-destinations" },
  { slug: "captures", titleKey: "exercises.captures.title", descKey: "exercises.captures.desc", status: "active", route: "/exercises/captures" },
  { slug: "hanging-pieces", titleKey: "exercises.hanging-pieces.title", descKey: "exercises.hanging-pieces.desc", status: "active", route: "/exercises/hanging-pieces" },
  { slug: "equal-attackers-defenders", titleKey: "exercises.equal-attackers-defenders.title", descKey: "exercises.equal-attackers-defenders.desc", status: "active", route: "/exercises/equal-attackers-defenders" },
  { slug: "castling-rights", titleKey: "exercises.castling-rights.title", descKey: "exercises.castling-rights.desc", status: "active", route: "/exercises/castling-rights" },
  { slug: "give-check", titleKey: "exercises.give-check.title", descKey: "exercises.give-check.desc", status: "coming_soon", route: null },
  { slug: "get-out-of-check", titleKey: "exercises.get-out-of-check.title", descKey: "exercises.get-out-of-check.desc", status: "coming_soon", route: null },
  { slug: "pathfinding", titleKey: "exercises.pathfinding.title", descKey: "exercises.pathfinding.desc", status: "coming_soon", route: null },
  { slug: "pin", titleKey: "exercises.pin.title", descKey: "exercises.pin.desc", status: "coming_soon", route: null },
  { slug: "balance-scale", titleKey: "exercises.balance-scale.title", descKey: "exercises.balance-scale.desc", status: "coming_soon", route: null },
  { slug: "heavier-side", titleKey: "exercises.heavier-side.title", descKey: "exercises.heavier-side.desc", status: "coming_soon", route: null },
  { slug: "is-checkmate", titleKey: "exercises.is-checkmate.title", descKey: "exercises.is-checkmate.desc", status: "coming_soon", route: null },
  { slug: "memory-board", titleKey: "exercises.memory-board.title", descKey: "exercises.memory-board.desc", status: "coming_soon", route: null },
  { slug: "blindfold-square-vision", titleKey: "exercises.blindfold-square-vision.title", descKey: "exercises.blindfold-square-vision.desc", status: "coming_soon", route: null },
  { slug: "blindfold-calculation", titleKey: "exercises.blindfold-calculation.title", descKey: "exercises.blindfold-calculation.desc", status: "coming_soon", route: null },
  { slug: "opening-traps-blindfold", titleKey: "exercises.opening-traps-blindfold.title", descKey: "exercises.opening-traps-blindfold.desc", status: "coming_soon", route: null },
  { slug: "reverse-opening", titleKey: "exercises.reverse-opening.title", descKey: "exercises.reverse-opening.desc", status: "coming_soon", route: null },
  { slug: "trapped-pieces", titleKey: "exercises.trapped-pieces.title", descKey: "exercises.trapped-pieces.desc", status: "coming_soon", route: null },
  { slug: "avoid-stalemate", titleKey: "exercises.avoid-stalemate.title", descKey: "exercises.avoid-stalemate.desc", status: "coming_soon", route: null },
  { slug: "square-rule", titleKey: "exercises.square-rule.title", descKey: "exercises.square-rule.desc", status: "coming_soon", route: null },
];

export function getExerciseMeta(slug: string): ExerciseMeta | undefined {
  return EXERCISE_CATALOG.find((entry) => entry.slug === slug);
}
