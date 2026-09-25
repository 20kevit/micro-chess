import { useEffect, useState, type ReactNode } from "react";
import type { AnswerContract } from "../../api/types";
import { t } from "../../i18n";
import { normalizeSquareName, normalizeUci } from "../../lib/fenEditor";

export type { AnswerContract };

interface AnswerEditorProps {
  contract: AnswerContract;
  answer: Record<string, unknown>;
  onChange: (answer: Record<string, unknown>) => void;
  disabled?: boolean;
}

const INPUT_CLASS = "min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm";
const PIECE_CODES = ["K", "Q", "R", "B", "N", "P"] as const;

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((entry): entry is string => typeof entry === "string");
}

function fieldLabel(name: string): string {
  if (name === "target") return t("admin.answerTarget");
  if (name === "from") return t("admin.label.start");
  if (name === "profile") return t("admin.label.category");
  if (name === "left") return t("balance.blackPan");
  if (name === "right") return t("balance.whitePan");
  if (name === "bank") return t("chineseBoard.palette");
  if (name === "piece") return t("admin.boardPieceCount");
  if (name === "optimal_moves") return t("pathfinding.moves");
  if (name === "start_fen") return t("admin.answerStartFen");
  if (name === "target_fen") return t("admin.answerTargetFen");
  if (name === "fen") return t("admin.position");
  if (name === "solution" || name === "move") return t("blindfoldCalculation.answer");
  if (name === "moves" || name === "solutions") return t("admin.review.answer");
  if (name === "squares" || name === "square" || name === "pin") return t("admin.review.answer");
  return t("admin.review.answer");
}

function fieldTitle(name: string): string {
  return `${fieldLabel(name)} · ${name}`;
}

function FieldTitle({ name }: { name: string }) {
  return (
    <p className="text-sm font-bold">
      {fieldLabel(name)} <code className="text-xs font-normal text-stone-500" dir="ltr">{name}</code>
    </p>
  );
}

function ChipList({
  items,
  onRemove,
  disabled,
}: {
  items: string[];
  onRemove: (index: number) => void;
  disabled: boolean;
}) {
  if (items.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1" dir="ltr">
      {items.map((item, index) => (
        <button
          key={`${item}-${index}`}
          type="button"
          disabled={disabled}
          onClick={() => {
            if (!disabled) onRemove(index);
          }}
          className="min-h-[36px] rounded-full bg-violet-100 px-3 font-mono text-xs font-bold text-violet-800 disabled:cursor-not-allowed disabled:opacity-70"
          title={String(index + 1)}
        >
          {index + 1}. {item} {disabled ? "" : "✕"}
        </button>
      ))}
    </div>
  );
}

function ListEditor({
  name,
  items,
  placeholder,
  validate,
  onChange,
  disabled,
  orderedLabels,
}: {
  name: string;
  items: string[];
  placeholder: string;
  validate: (raw: string) => string | null;
  onChange: (items: string[]) => void;
  disabled: boolean;
  orderedLabels?: string[];
}) {
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  function add() {
    const parts = draft.split(/[\s,;]+/).filter(Boolean);
    if (parts.length === 0) return;
    const normalized: string[] = [];
    for (const part of parts) {
      const clean = validate(part);
      if (!clean) {
        setError(`${t("admin.answerInvalid")}: ${part}`);
        return;
      }
      normalized.push(clean);
    }
    setError("");
    setDraft("");
    onChange([...items, ...normalized]);
  }

  return (
    <div>
      <FieldTitle name={name} />
      {orderedLabels ? (
        <ul className="mt-2 flex flex-col gap-1" dir="ltr">
          {items.map((item, index) => (
            <li
              key={`${item}-${index}`}
              className="flex min-h-[44px] items-center justify-between rounded-xl bg-stone-50 px-3 font-mono text-sm"
            >
              <span>
                {orderedLabels[index] ?? `#${index + 1}`}: <b>{item}</b>
              </span>
              <button
                type="button"
                disabled={disabled}
                onClick={() => onChange(items.filter((_, i) => i !== index))}
                className="min-h-[36px] min-w-[36px] font-bold text-red-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                ✕
              </button>
            </li>
          ))}
          {items.length === 0 ? <li className="text-xs text-stone-400">{t("admin.empty")}</li> : null}
        </ul>
      ) : (
        <ChipList
          items={items}
          disabled={disabled}
          onRemove={(index) => onChange(items.filter((_, itemIndex) => itemIndex !== index))}
        />
      )}
      <div className="mt-2 flex gap-2" dir="ltr">
        <input
          value={draft}
          disabled={disabled}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          aria-label={fieldTitle(name)}
          className={`${INPUT_CLASS} flex-1 font-mono`}
        />
        <button
          type="button"
          disabled={disabled}
          onClick={add}
          aria-label={t("admin.review.select")}
          className="min-h-[44px] rounded-xl bg-violet-700 px-4 text-sm font-bold text-white disabled:opacity-50"
        >
          +
        </button>
      </div>
      {error ? <p className="mt-1 text-xs font-bold text-red-600">{error}</p> : null}
    </div>
  );
}

function TextField({
  name,
  value,
  onChange,
  disabled,
}: {
  name: string;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  const text = value === undefined || value === null ? "" : String(value);
  function update(raw: string) {
    if (name === "from" || name === "square") {
      onChange(normalizeSquareName(raw) ?? raw);
    } else if (name === "move" || name === "solution") {
      onChange(normalizeUci(raw) ?? raw);
    } else if (["optimal_moves", "optimal_count", "piece_count", "memorization_ms"].includes(name)) {
      onChange(raw === "" ? "" : Number(raw));
    } else {
      onChange(raw);
    }
  }
  if (name === "side_to_move") {
    return (
      <div>
        <label className="block text-sm font-bold" htmlFor={`answer-${name}`}>{fieldTitle(name)}</label>
        <select id={`answer-${name}`} disabled={disabled} value={text || "w"} onChange={(event) => update(event.target.value)} className={`${INPUT_CLASS} mt-1 w-full`} dir="ltr">
          <option value="w">{t("admin.boardWhite")}</option>
          <option value="b">{t("admin.boardBlack")}</option>
        </select>
      </div>
    );
  }
  if (name === "profile") {
    return (
      <div>
        <label className="block text-sm font-bold" htmlFor={`answer-${name}`}>{fieldTitle(name)}</label>
        <select id={`answer-${name}`} disabled={disabled} value={text || "standard"} onChange={(event) => update(event.target.value)} className={`${INPUT_CLASS} mt-1 w-full`} dir="ltr">
          <option value="standard">{t("admin.editor.ruleProfileStandard")}</option>
          <option value="ignore-enemy-attacks">{t("admin.editor.ruleProfileIgnoreEnemyAttacks")}</option>
        </select>
      </div>
    );
  }
  if (["description_fa", "opening_fa", "trap_fa", "theme_fa"].includes(name)) {
    return (
      <div>
        <label className="block text-sm font-bold" htmlFor={`answer-${name}`}>{fieldTitle(name)}</label>
        <textarea id={`answer-${name}`} disabled={disabled} value={text} onChange={(event) => update(event.target.value)} rows={3} className="mt-1 w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm" />
      </div>
    );
  }
  return (
    <div>
      <label className="block text-sm font-bold" htmlFor={`answer-${name}`}>
        {fieldTitle(name)}
      </label>
      <input
        id={`answer-${name}`}
        dir="ltr"
        disabled={disabled}
        value={text}
        onChange={(event) => update(event.target.value)}
        className={`${INPUT_CLASS} mt-1 w-full font-mono`}
      />
    </div>
  );
}

function optionLabel(contract: AnswerContract, option: string): string {
  if (contract.exercise_slug === "is-checkmate") {
    if (option === "checkmate") return t("checkmate.checkmate");
    if (option === "check") return t("checkmate.check");
    if (option === "not_check") return t("checkmate.notCheck");
  }
  if (contract.exercise_slug === "heavier-side") {
    if (option === "white") return t("heavierSide.white");
    if (option === "black") return t("heavierSide.black");
    if (option === "equal") return t("heavierSide.equal");
  }
  if (option === "white_kingside") return t("castling.white_kingside");
  if (option === "white_queenside") return t("castling.white_queenside");
  if (option === "black_kingside") return t("castling.black_kingside");
  if (option === "black_queenside") return t("castling.black_queenside");
  return option;
}

function OptionControl({
  contract,
  name,
  options,
  selected,
  multiple,
  onChange,
  disabled,
}: {
  contract: AnswerContract;
  name: string;
  options: string[];
  selected: string[];
  multiple: boolean;
  onChange: (values: string[]) => void;
  disabled: boolean;
}) {
  const active = new Set(selected);
  return (
    <div>
      <FieldTitle name={name} />
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2" dir="ltr">
        {options.map((option) => {
          const isActive = active.has(option);
          return (
            <button
              key={option}
              type="button"
              disabled={disabled}
              onClick={() => {
                if (!multiple) {
                  onChange([option]);
                  return;
                }
                const next = new Set(selected);
                if (next.has(option)) next.delete(option);
                else next.add(option);
                onChange([...next]);
              }}
              className={`min-h-[44px] rounded-xl border px-3 text-sm font-bold ${
                isActive ? "border-violet-700 bg-violet-700 text-white" : "border-stone-200 bg-white"
              }`}
            >
              <span>{optionLabel(contract, option)}</span>{" "}
              <code className="text-xs font-normal opacity-75">{option}</code>
            </button>
          );
        })}
      </div>
    </div>
  );
}

interface Placement {
  color: string;
  piece: string;
  square: string;
}

function placementList(value: unknown): Placement[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const row = entry as Record<string, unknown>;
    return [{
      color: typeof row.color === "string" ? row.color : "white",
      piece: typeof row.piece === "string" ? row.piece.toUpperCase() : "P",
      square: typeof row.square === "string" ? row.square : "",
    }];
  });
}

function PlacementEditor({
  name,
  value,
  onChange,
  disabled,
}: {
  name: string;
  value: unknown;
  onChange: (value: Placement[]) => void;
  disabled: boolean;
}) {
  const placements = placementList(value);
  function update(index: number, patch: Partial<Placement>) {
    onChange(placements.map((entry, itemIndex) => itemIndex === index ? { ...entry, ...patch } : entry));
  }
  return (
    <div>
      <FieldTitle name={name} />
      <div className="mt-2 flex flex-col gap-2">
        {placements.map((placement, index) => (
          <div key={`${placement.square}-${index}`} className="grid grid-cols-3 gap-2">
            <select
              aria-label={`${t("admin.boardPieceCount")} ${index + 1}`}
              value={placement.color}
              disabled={disabled}
              onChange={(event) => update(index, { color: event.target.value })}
              className={INPUT_CLASS}
            >
              <option value="white">{t("admin.boardWhite")}</option>
              <option value="black">{t("admin.boardBlack")}</option>
            </select>
            <select
              aria-label={`${t("admin.boardPieceCount")} ${index + 1}`}
              value={placement.piece}
              disabled={disabled}
              onChange={(event) => update(index, { piece: event.target.value })}
              className={`${INPUT_CLASS} font-mono`}
              dir="ltr"
            >
              {PIECE_CODES.map((piece) => <option key={piece} value={piece}>{piece}</option>)}
            </select>
            <input
              aria-label={`${t("admin.position")} ${index + 1}`}
              value={placement.square}
              disabled={disabled}
              onChange={(event) => update(index, { square: normalizeSquareName(event.target.value) ?? event.target.value })}
              className={`${INPUT_CLASS} font-mono`}
              dir="ltr"
            />
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-2">
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange([...placements, { color: "white", piece: "P", square: "" }])}
          className="min-h-[44px] rounded-xl bg-violet-700 px-4 text-sm font-bold text-white disabled:opacity-50"
        >
          +
        </button>
        {placements.length > 0 ? (
          <button
            type="button"
            disabled={disabled}
            onClick={() => onChange(placements.slice(0, -1))}
            className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-4 text-sm font-bold text-red-700 disabled:opacity-50"
          >
            {t("profile.remove")}
          </button>
        ) : null}
      </div>
    </div>
  );
}

interface EnemyPiece {
  square: string;
  kind: string;
}

function enemyList(value: unknown): EnemyPiece[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) return [];
    const row = entry as Record<string, unknown>;
    return [{
      square: typeof row.square === "string" ? row.square : "",
      kind: typeof row.kind === "string" ? row.kind.toLowerCase() : "pawn",
    }];
  });
}

function EnemyListEditor({
  name,
  value,
  onChange,
  disabled,
}: {
  name: string;
  value: unknown;
  onChange: (value: EnemyPiece[]) => void;
  disabled: boolean;
}) {
  const enemies = enemyList(value);
  function update(index: number, patch: Partial<EnemyPiece>) {
    onChange(enemies.map((entry, itemIndex) => itemIndex === index ? { ...entry, ...patch } : entry));
  }
  return (
    <div>
      <FieldTitle name={name} />
      <div className="mt-2 flex flex-col gap-2">
        {enemies.map((enemy, index) => (
          <div key={`${enemy.square}-${index}`} className="grid grid-cols-2 gap-2">
            <input
              aria-label={`${t("admin.position")} ${index + 1}`}
              value={enemy.square}
              disabled={disabled}
              onChange={(event) => update(index, { square: normalizeSquareName(event.target.value) ?? event.target.value })}
              className={INPUT_CLASS}
              dir="ltr"
            />
            <select
              aria-label={`${t("admin.label.category")} ${index + 1}`}
              value={enemy.kind}
              disabled={disabled}
              onChange={(event) => update(index, { kind: event.target.value })}
              className={INPUT_CLASS}
              dir="ltr"
            >
              <option value="pawn">{t("pieces.pawn")}</option>
              <option value="knight">{t("pieces.knight")}</option>
              <option value="bishop">{t("pieces.bishop")}</option>
              <option value="rook">{t("pieces.rook")}</option>
              <option value="queen">{t("pieces.queen")}</option>
            </select>
          </div>
        ))}
      </div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange([...enemies, { square: "", kind: "pawn" }])}
        className="mt-2 min-h-[44px] rounded-xl bg-violet-700 px-4 text-sm font-bold text-white disabled:opacity-50"
      >
        +
      </button>
      {enemies.length > 0 ? (
        <button
          type="button"
          disabled={disabled}
          onClick={() => onChange(enemies.slice(0, -1))}
          className="mt-2 min-h-[44px] rounded-xl border border-stone-200 px-4 text-sm font-bold text-red-700 disabled:opacity-50"
        >
          {t("profile.remove")}
        </button>
      ) : null}
    </div>
  );
}

function listPlaceholder(name: string, contract: AnswerContract, items: string[]): string {
  if (name === "pin") return "e8";
  if (name === "squares") return "e4";
  if (name === "moves" || name === "solutions") return "e2e4";
  if (name === "bank" || name === "left" || name === "right") return "N P";
  if (contract.answer_fields.find((field) => field.name === name)?.item_hint) {
    return String(contract.answer_fields.find((field) => field.name === name)?.item_hint);
  }
  return items[0] ?? name;
}

function normalizeListValue(name: string, raw: string): string | null {
  if (name === "squares" || name === "pin" || name === "from" || name === "square") {
    return normalizeSquareName(raw);
  }
  if (name === "moves" || name === "solutions" || name === "move" || name === "solution") {
    return normalizeUci(raw);
  }
  if (name === "bank" || name === "left" || name === "right" || name === "piece") {
    const normalized = raw.trim().toUpperCase();
    return /^[PNBRQK]$/.test(normalized) ? normalized : null;
  }
  return raw.trim() || null;
}

function DeclaredFields({
  contract,
  answer,
  onChange,
  disabled,
  exclude = [],
}: {
  contract: AnswerContract;
  answer: Record<string, unknown>;
  onChange: (answer: Record<string, unknown>) => void;
  disabled: boolean;
  exclude?: string[];
}) {
  function set(name: string, value: unknown) {
    onChange({ ...answer, [name]: value });
  }

  const rendered = contract.answer_fields
    .filter((field) => !exclude.includes(field.name))
    .filter((field) => !(field.name === "fen" && contract.needs_board))
    .map((field): ReactNode => {
      if (field.kind === "string_list") {
        const items = asStringList(answer[field.name]);
        const ordered = field.name === "pin"
          ? [t("admin.pinPinner"), t("admin.pinPinned"), t("admin.pinBehind")]
          : undefined;
        return (
          <ListEditor
            key={field.name}
            name={field.name}
            items={items}
            placeholder={listPlaceholder(field.name, contract, items)}
            validate={(raw) => normalizeListValue(field.name, raw)}
            onChange={(next) => set(field.name, next)}
            disabled={disabled}
            orderedLabels={ordered}
          />
        );
      }
      if (field.kind === "option_list") {
        return (
          <OptionControl
            key={field.name}
            contract={contract}
            name={field.name}
            options={field.options ?? []}
            selected={asStringList(answer[field.name])}
            multiple
            onChange={(next) => set(field.name, next)}
            disabled={disabled}
          />
        );
      }
      if (field.kind === "integer") {
        return <TextField key={field.name} name={field.name} value={answer[field.name]} onChange={(value) => set(field.name, value)} disabled={disabled} />;
      }
      if (field.kind === "placement_list") {
        return <PlacementEditor key={field.name} name={field.name} value={answer[field.name]} onChange={(value) => set(field.name, value)} disabled={disabled} />;
      }
      if (field.kind === "enemy_list") {
        return <EnemyListEditor key={field.name} name={field.name} value={answer[field.name]} onChange={(value) => set(field.name, value)} disabled={disabled} />;
      }
      if (field.kind === "string") {
        return <TextField key={field.name} name={field.name} value={answer[field.name]} onChange={(value) => set(field.name, value)} disabled={disabled} />;
      }
      return null;
    });

  return <div className="flex flex-col gap-3">{rendered}</div>;
}

export function PositionDataEditor({
  contract,
  value,
  onChange,
  disabled = false,
}: {
  contract: AnswerContract;
  value: Record<string, unknown>;
  onChange: (value: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  const positionContract: AnswerContract = {
    ...contract,
    answer_fields: contract.position_fields,
  };
  return (
    <DeclaredFields
      contract={positionContract}
      answer={value}
      onChange={onChange}
      disabled={disabled}
    />
  );
}

function choiceOptions(contract: AnswerContract): string[] {
  if (contract.exercise_slug === "is-checkmate") return ["checkmate", "check", "not_check"];
  if (contract.exercise_slug === "heavier-side") return ["white", "black", "equal"];
  const field = contract.answer_fields.find((entry) => entry.name === "choice");
  return field?.options ?? [];
}

function ChoiceControl({
  contract,
  answer,
  onChange,
  disabled,
}: {
  contract: AnswerContract;
  answer: Record<string, unknown>;
  onChange: (answer: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const options = choiceOptions(contract);
  const current = typeof answer["choice"] === "string" ? answer["choice"] : "";
  if (options.length === 0) {
    return <TextField name="choice" value={current} onChange={(value) => onChange({ ...answer, choice: value })} disabled={disabled} />;
  }
  return (
    <OptionControl
      contract={contract}
      name="choice"
      options={options}
      selected={current ? [current] : []}
      multiple={false}
      onChange={(values) => onChange({ ...answer, choice: values[0] ?? "" })}
      disabled={disabled}
    />
  );
}

function SequenceEditor({
  contract,
  answer,
  onChange,
  disabled,
}: {
  contract: AnswerContract;
  answer: Record<string, unknown>;
  onChange: (answer: Record<string, unknown>) => void;
  disabled: boolean;
}) {
  const raw = answer["solutions"];
  const sequences = Array.isArray(raw)
    ? raw.map((sequence) => asStringList(sequence))
    : [];
  function update(index: number, moves: string[]) {
    onChange({ ...answer, solutions: sequences.map((entry, itemIndex) => itemIndex === index ? moves : entry) });
  }
  return (
    <div className="flex flex-col gap-4">
      <DeclaredFields
        contract={contract}
        answer={answer}
        onChange={onChange}
        disabled={disabled}
        exclude={contract.needs_board ? ["solutions", "target_fen"] : ["solutions"]}
      />
      {sequences.map((sequence, sequenceIndex) => (
        <div key={`sequence-${sequenceIndex}`} className="rounded-2xl bg-stone-50 p-3">
          <div className="mb-2 flex items-center justify-between gap-2">
            <p className="font-bold">{t("admin.review.answer")} · {sequenceIndex + 1}</p>
            <button
              type="button"
              disabled={disabled}
              onClick={() => onChange({
                ...answer,
                solutions: sequences.filter((_, index) => index !== sequenceIndex),
              })}
              className="min-h-[44px] rounded-xl bg-white px-3 text-sm font-bold text-red-700 disabled:opacity-50"
            >
              {t("profile.remove")}
            </button>
          </div>
          <ListEditor
            name="solutions"
            items={sequence}
            placeholder="e2e4"
            validate={uciValidator}
            onChange={(moves) => update(sequenceIndex, moves)}
            disabled={disabled}
            orderedLabels={sequence.map((_, moveIndex) => String(moveIndex + 1))}
          />
        </div>
      ))}
      <button
        type="button"
        disabled={disabled}
        onClick={() => onChange({ ...answer, solutions: [...sequences, []] })}
        className="min-h-[44px] rounded-xl bg-violet-700 px-4 text-sm font-bold text-white disabled:opacity-50"
      >
        +
      </button>
    </div>
  );
}

const uciValidator = (raw: string) => normalizeUci(raw);

export function synchronizeAnswerFen(
  contract: AnswerContract,
  answer: Record<string, unknown>,
  fen: string | null,
): Record<string, unknown> {
  const next = { ...answer };
  if (!contract.needs_board || !fen) return next;
  const names = new Set(contract.answer_fields.map((field) => field.name));
  if (contract.fen_derived && names.has("fen")) next["fen"] = fen;
  if (names.has("start_fen") && names.has("target_fen")) next["target_fen"] = fen;
  return next;
}

export function AnswerEditor({ contract, answer, onChange, disabled = false }: AnswerEditorProps) {
  const supportedKinds = new Set(["string", "string_list", "option_list", "integer", "move_sequence_list", "placement_list", "enemy_list"]);
  const hasUnsupportedField = contract.answer_fields.some(
    (field) => !supportedKinds.has(field.kind) && !(field.name === "fen" && contract.needs_board),
  );

  let editor: ReactNode;
  if (contract.answer_type === "move_sequence") {
    editor = <SequenceEditor contract={contract} answer={answer} onChange={onChange} disabled={disabled} />;
  } else if (contract.answer_type === "choice") {
    editor = (
      <div className="flex flex-col gap-3">
        <DeclaredFields contract={contract} answer={answer} onChange={onChange} disabled={disabled} />
        {contract.fen_derived ? (
          <p className="rounded-xl bg-stone-50 p-3 text-xs text-stone-600">{t("admin.answerDerivedNote")}</p>
        ) : (
          <ChoiceControl contract={contract} answer={answer} onChange={onChange} disabled={disabled} />
        )}
      </div>
    );
  } else if (contract.answer_type === "options") {
    editor = <DeclaredFields contract={contract} answer={answer} onChange={onChange} disabled={disabled} />;
  } else if (contract.answer_type === "square_or_color") {
    editor = (
      <div className="flex flex-col gap-3">
        <DeclaredFields contract={contract} answer={answer} onChange={onChange} disabled={disabled} />
        {contract.fen_derived ? <p className="text-xs text-stone-500">{t("admin.answerDerivedNote")}</p> : null}
      </div>
    );
  } else if (contract.answer_type === "placements" && !hasUnsupportedField) {
    editor = (
      <div className="flex flex-col gap-3">
        <DeclaredFields contract={contract} answer={answer} onChange={onChange} disabled={disabled} />
        {contract.fen_derived ? <p className="text-xs text-stone-500">{t("admin.answerDerivedNote")}</p> : null}
      </div>
    );
  } else {
    editor = <DeclaredFields contract={contract} answer={answer} onChange={onChange} disabled={disabled} />;
  }

  if (hasUnsupportedField) {
    editor = (
      <div className="flex flex-col gap-3">
        {editor}
        <StructuredAnswerEditor answer={answer} onChange={onChange} disabled={disabled} />
      </div>
    );
  }
  return <div>{editor}</div>;
}

export function StructuredAnswerEditor({
  answer,
  onChange,
  disabled = false,
}: {
  answer: Record<string, unknown>;
  onChange: (answer: Record<string, unknown>) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState(() => JSON.stringify(answer, null, 2));
  const [error, setError] = useState("");

  useEffect(() => {
    setText(JSON.stringify(answer, null, 2));
  }, [answer]);

  function apply() {
    try {
      const parsed: unknown = JSON.parse(text);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        setError(t("admin.answerJsonObject"));
        return;
      }
      setError("");
      onChange(parsed as Record<string, unknown>);
    } catch {
      setError(t("admin.answerInvalid"));
    }
  }

  return (
    <div>
      <textarea
        dir="ltr"
        disabled={disabled}
        value={text}
        onChange={(event) => setText(event.target.value)}
        rows={8}
        className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 py-2 font-mono text-xs"
      />
      {error ? <p className="mt-1 text-xs font-bold text-red-600">{error}</p> : null}
      <button
        type="button"
        disabled={disabled}
        onClick={apply}
        className="mt-2 min-h-[44px] rounded-xl bg-violet-700 px-4 text-sm font-bold text-white disabled:opacity-50"
      >
        {t("admin.answerApplyJson")}
      </button>
    </div>
  );
}

export function answerSummary(answer: Record<string, unknown>): string {
  try {
    const text = JSON.stringify(answer);
    return text.length > 500 ? `${text.slice(0, 500)}…` : text;
  } catch {
    return "—";
  }
}
