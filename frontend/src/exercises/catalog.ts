import type { FaKey } from "../i18n/fa";

// Central exercise catalog: every exercise has one entry with its slug,
// translation keys, availability status, and route (when playable).
// Pages render from status — never from per-slug conditionals — so adding
// an exercise means appending one entry here, not touching components.
//
// Order follows the official MicroChess roadmap (Exercises 1–18 + 21;
// 19 avoid-stalemate and 20 rule-of-the-square were removed).

export type ExerciseStatus = "active" | "coming_soon";

export interface ExerciseMeta {
  slug: string;
  titleKey: FaKey;
  descKey: FaKey;
  status: ExerciseStatus;
  /** Playable route. Null while coming soon (card renders without a link). */
  route: string | null;
  /** Explicit entry modes (e.g. practice vs speed). When present, the card
   * renders one button per mode instead of a single ambiguous start button. */
  modes?: ExerciseEntryMode[];
}

export interface ExerciseEntryMode {
  id: string;
  labelKey: FaKey;
  descKey: FaKey;
  /** Query string appended to the route, e.g. "?mode=speed". */
  params: string;
}

export const EXERCISE_CATALOG: ExerciseMeta[] = [
  {
    slug: "piece-recognition",
    titleKey: "exercises.piece-recognition.title",
    descKey: "exercises.piece-recognition.desc",
    status: "active",
    route: "/exercises/piece-recognition",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "legal-destinations",
    titleKey: "exercises.legal-destinations.title",
    descKey: "exercises.legal-destinations.desc",
    status: "active",
    route: "/exercises/legal-destinations",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "captures",
    titleKey: "exercises.captures.title",
    descKey: "exercises.captures.desc",
    status: "active",
    route: "/exercises/captures",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "undefended-pieces",
    titleKey: "exercises.undefended-pieces.title",
    descKey: "exercises.undefended-pieces.desc",
    status: "active",
    route: "/exercises/undefended-pieces",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "give-check",
    titleKey: "exercises.give-check.title",
    descKey: "exercises.give-check.desc",
    status: "active",
    route: "/exercises/give-check",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "get-out-of-check",
    titleKey: "exercises.get-out-of-check.title",
    descKey: "exercises.get-out-of-check.desc",
    status: "active",
    route: "/exercises/get-out-of-check",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "pathfinding",
    titleKey: "exercises.pathfinding.title",
    descKey: "exercises.pathfinding.desc",
    status: "active",
    route: "/exercises/pathfinding",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  {
    slug: "pathfinding-obstacles",
    titleKey: "exercises.pathfinding-obstacles.title",
    descKey: "exercises.pathfinding-obstacles.desc",
    status: "active",
    route: "/exercises/pathfinding-obstacles",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  { slug: "balance-scale", titleKey: "exercises.balance-scale.title", descKey: "exercises.balance-scale.desc", status: "active", route: "/exercises/balance-scale",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  { slug: "heavier-side", titleKey: "exercises.heavier-side.title", descKey: "exercises.heavier-side.desc", status: "active", route: "/exercises/heavier-side",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  { slug: "pin", titleKey: "exercises.pin.title", descKey: "exercises.pin.desc", status: "active", route: "/exercises/pin" },
  { slug: "chinese-board", titleKey: "exercises.chinese-board.title", descKey: "exercises.chinese-board.desc", status: "active", route: "/exercises/chinese-board",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  { slug: "is-checkmate", titleKey: "exercises.is-checkmate.title", descKey: "exercises.is-checkmate.desc", status: "active", route: "/exercises/is-checkmate" },
  { slug: "blindfold-square-vision", titleKey: "exercises.blindfold-square-vision.title", descKey: "exercises.blindfold-square-vision.desc", status: "active", route: "/exercises/blindfold-square-vision",
    modes: [
      { id: "practice", labelKey: "play.practice", descKey: "practice.howto", params: "?mode=practice" },
      { id: "speed", labelKey: "play.speed", descKey: "speed.howto", params: "?mode=speed" },
    ],
  },
  { slug: "blindfold-calculation", titleKey: "exercises.blindfold-calculation.title", descKey: "exercises.blindfold-calculation.desc", status: "active", route: "/exercises/blindfold-calculation" },
  { slug: "opening-traps", titleKey: "exercises.opening-traps.title", descKey: "exercises.opening-traps.desc", status: "active", route: "/exercises/opening-traps" },
  { slug: "reverse-opening", titleKey: "exercises.reverse-opening.title", descKey: "exercises.reverse-opening.desc", status: "active", route: "/exercises/reverse-opening" },
  { slug: "trapped-pieces", titleKey: "exercises.trapped-pieces.title", descKey: "exercises.trapped-pieces.desc", status: "active", route: "/exercises/trapped-pieces" },
  { slug: "castling-rights", titleKey: "exercises.castling-rights.title", descKey: "exercises.castling-rights.desc", status: "active", route: "/exercises/castling-rights" },
];

export function getExerciseMeta(slug: string): ExerciseMeta | undefined {
  return EXERCISE_CATALOG.find((entry) => entry.slug === slug);
}
