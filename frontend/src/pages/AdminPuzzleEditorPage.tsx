import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type {
  AdminExercise,
  AdminPuzzle,
  AnswerContract,
  PreviewValidation,
  PuzzleHistory,
  PuzzleUsage,
} from "../api/types";
import { ChessBoard } from "../components/chess/ChessBoard";
import {
  AnswerEditor,
  PositionDataEditor,
  StructuredAnswerEditor,
  answerSummary,
  synchronizeAnswerFen,
} from "../components/content/AnswerEditor";
import { BoardEditor } from "../components/content/BoardEditor";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { fenToPieces } from "../lib/fen";
import { START_FEN, parseFen } from "../lib/fenEditor";
import { faNum } from "../lib/playerDisplay";

const MEANING_LOCKED = new Set(["published", "retired", "archived", "rejected", "quarantined"]);
const METADATA_LOCKED = new Set(["retired", "archived", "rejected", "quarantined"]);

function statusLabel(status: string | null): string {
  if (status === "validated") return t("admin.statusValidated");
  if (status === "reviewed") return t("admin.statusReviewed");
  if (status === "approved") return t("admin.statusApproved");
  if (status === "published") return t("admin.statusPublished");
  if (status === "quarantined") return t("admin.status.quarantined");
  if (status === "rejected") return t("admin.status.rejected");
  if (status === "retired" || status === "archived") return t("admin.status.retired");
  return t("admin.statusDraft");
}

function sourceLabel(source: string): string {
  if (source === "manual") return t("admin.sourceManual");
  if (source === "generated") return t("admin.sourceGenerated");
  if (source === "imported") return t("admin.sourceImported");
  return t("admin.unknown");
}

const AUTO_POSITION_FIELDS = new Set([
  "fen",
  "start_fen",
  "target_fen",
  "from",
  "target",
  "piece",
  "enemies",
  "left",
  "profile",
  "square",
  "side_to_move",
  "piece_count",
  "memorization_ms",
]);

export function AdminPuzzleEditorPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const parsedId = id === undefined ? null : Number(id);
  const editingId = parsedId !== null && Number.isInteger(parsedId) && parsedId > 0 ? parsedId : null;
  const invalidId = id !== undefined && editingId === null;
  const isNew = editingId === null;
  const requestedExercise = searchParams.get("exercise") ?? "";

  const [exercises, setExercises] = useState<AdminExercise[]>([]);
  const [slug, setSlug] = useState(requestedExercise);
  const [contract, setContract] = useState<AnswerContract | null>(null);
  const [existing, setExisting] = useState<AdminPuzzle | null>(null);
  const [history, setHistory] = useState<PuzzleHistory | null>(null);
  const [usage, setUsage] = useState<PuzzleUsage | null>(null);
  const [positionJson, setPositionJson] = useState<Record<string, unknown>>({});
  const [hintJson, setHintJson] = useState<Record<string, unknown>>({});
  const [fen, setFen] = useState<string | null>(START_FEN);
  const [answer, setAnswer] = useState<Record<string, unknown>>({});
  const [difficulty, setDifficulty] = useState("");
  const [rating, setRating] = useState("1200");
  const [targetRating, setTargetRating] = useState("");
  const [sourceReference, setSourceReference] = useState("");
  const [prompt, setPrompt] = useState("");
  const [explanation, setExplanation] = useState("");
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [preview, setPreview] = useState<PreviewValidation | null>(null);

  useEffect(() => {
    let active = true;
    adminApi.exercises({})
      .then((rows) => {
        if (!active) return;
         setExercises(rows);
         if (!requestedExercise && rows.length > 0) setSlug((current) => current || rows[0].slug);
      })
      .catch(() => {
        if (active) setExercises([]);
      });
    return () => {
      active = false;
    };
  }, [requestedExercise]);

  useEffect(() => {
    if (!isNew) return;
    let active = true;
    setContract(null);
    if (!slug) return;
    adminApi.answerContract(slug)
      .then((next) => {
        if (active) setContract(next);
      })
      .catch(() => {
        if (active) setContract(null);
      });
    return () => {
      active = false;
    };
  }, [isNew, slug]);

  useEffect(() => {
    if (isNew) {
      setExisting(null);
      setHistory(null);
      setUsage(null);
      setAnswer({});
      setPositionJson({});
      setHintJson({});
      setPreview(null);
    }
  }, [editingId, isNew]);

  useEffect(() => {
    if (invalidId) {
      setFailed(true);
      setLoading(false);
      return;
    }
    if (isNew) {
      setLoading(false);
      return;
    }
    if (editingId === null) {
      setFailed(true);
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setFailed(false);
    adminApi.puzzle(editingId)
      .then(async (row) => {
        const [nextContract, nextHistory, nextUsage] = await Promise.all([
          adminApi.answerContract(row.exercise_slug).catch(() => null),
          adminApi.puzzleHistory(editingId).catch(() => null),
          adminApi.puzzleUsage(editingId).catch(() => null),
        ]);
        return { row, nextContract, nextHistory, nextUsage };
      })
      .then(({ row, nextContract, nextHistory, nextUsage }) => {
        if (!active) return;
        setExisting(row);
        setSlug(row.exercise_slug);
        setContract(nextContract);
        setHistory(nextHistory);
        setUsage(nextUsage);
        setPositionJson(row.position_json ?? {});
        setHintJson(row.hint_json ?? {});
        setFen(row.fen);
        setAnswer(row.answer_json ?? {});
        setDifficulty(row.difficulty === null || row.difficulty === undefined ? "" : String(row.difficulty));
        setRating(String(row.initial_rating ?? 1200));
        setTargetRating(row.target_rating === null || row.target_rating === undefined ? "" : String(row.target_rating));
        setSourceReference(row.source_reference ?? "");
        setPrompt(row.prompt_fa ?? "");
        setExplanation(row.explanation ?? "");
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setFailed(true);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [editingId, invalidId, isNew]);

  const meaningLocked = existing ? MEANING_LOCKED.has(existing.status) : false;
  const metadataLocked = existing ? METADATA_LOCKED.has(existing.status) : false;
  const showBoard = contract?.needs_board ?? true;
  const canDeleteDraft = Boolean(
    existing
    && history
    && usage
    && existing.source === "manual"
    && existing.status === "draft"
    && !existing.is_published
    && !existing.is_archived
    && existing.generator_run_id === null
    && history.transitions.length === 0
    && history.validations.length === 0
    && history.reviews.length === 0
    && usage.attempts === 0,
  );

  const buildAnswer = useCallback((): Record<string, unknown> => {
    if (!contract) return { ...answer };
    const next = synchronizeAnswerFen(contract, answer, showBoard ? fen : null);
    if (contract.answer_fields.some((field) => field.name === "profile") && !next.profile) {
      next.profile = "standard";
    }
    return next;
  }, [answer, contract, fen, showBoard]);

  const buildPosition = useCallback((): Record<string, unknown> => {
    if (!contract) return { ...positionJson };
    const answerPayload = buildAnswer();
    const next = { ...positionJson };
    for (const field of contract.position_fields) {
      if (field.name in answerPayload) next[field.name] = answerPayload[field.name];
      else if (field.name === "mode" && !next.mode && field.item_hint) next.mode = field.item_hint;
    }
    const names = new Set(contract.position_fields.map((field) => field.name));
    const boardFen = showBoard ? fen : typeof answerPayload.fen === "string" ? answerPayload.fen : null;
    if (names.has("fen") && boardFen) next.fen = boardFen;
    if (names.has("start_fen") && typeof answerPayload.start_fen === "string") next.start_fen = answerPayload.start_fen;
    if (names.has("target_fen") && showBoard && fen) next.target_fen = fen;
    const parsed = boardFen ? parseFen(boardFen) : null;
    if (names.has("side_to_move") && parsed) next.side_to_move = parsed.turn;
    if (names.has("piece_count") && boardFen) next.piece_count = Object.keys(fenToPieces(boardFen)).length;
    if (names.has("memorization_ms") && boardFen) {
      next.memorization_ms = Object.keys(fenToPieces(boardFen)).length * 1000;
    }
    return next;
  }, [buildAnswer, contract, fen, positionJson, showBoard]);

  function metadataValues(): { level: number | null; initial: number; target: number | null } | null {
    const level = difficulty.trim() === "" ? null : Number(difficulty);
    if (level !== null && (!Number.isInteger(level) || level < 1 || level > 5)) {
      setNotice(t("admin.difficultyHint"));
      return null;
    }
    const initial = Number(rating);
    if (!Number.isFinite(initial) || initial < 100 || initial > 3000) {
      setNotice(t("admin.ratingHint"));
      return null;
    }
    const target = targetRating.trim() === "" ? null : Number(targetRating);
    if (target !== null && (!Number.isFinite(target) || target < 100 || target > 3000)) {
      setNotice(t("admin.ratingHint"));
      return null;
    }
    return { level, initial, target };
  }

  function boardIsValid(): boolean {
    if (!showBoard || !fen) return true;
    if (parseFen(fen)) return true;
    setNotice(t("admin.boardInvalidFen"));
    return false;
  }

  async function onValidate() {
    if (!slug || !contract) {
      setNotice(t("common.error"));
      return;
    }
    if (!boardIsValid()) return;
    const metadata = metadataValues();
    if (!metadata) return;
    setBusy(true);
    setNotice("");
    try {
      const finalPosition = buildPosition();
      const result = await adminApi.previewValidate({
        exercise_slug: slug,
        fen: showBoard ? fen : null,
        position_json: finalPosition,
        answer_json: buildAnswer(),
        difficulty: metadata.level,
        target_rating: metadata.target,
        initial_rating: metadata.initial,
        prompt_fa: prompt,
        explanation,
        exclude_puzzle_id: existing?.id,
      });
      setPreview(result);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onSave() {
    if (!slug || !contract) {
      setNotice(t("common.error"));
      return;
    }
    if (!boardIsValid()) return;
    const metadata = metadataValues();
    if (!metadata) return;
    setBusy(true);
    setNotice("");
    try {
      const finalAnswer = buildAnswer();
      const finalPosition = buildPosition();
      let row: AdminPuzzle;
      if (isNew) {
        row = await adminApi.createPuzzle({
          exercise_slug: slug,
          fen: showBoard ? fen : null,
          position_json: finalPosition,
          answer_json: finalAnswer,
          hint_json: hintJson,
          prompt_fa: prompt,
          explanation,
          initial_rating: metadata.initial,
          difficulty: metadata.level,
          target_rating: metadata.target,
          source_reference: sourceReference.trim() || undefined,
        });
      } else {
        if (!existing) throw new Error("missing_puzzle");
        const patch: Record<string, unknown> = {
          prompt_fa: prompt,
          explanation,
          initial_rating: metadata.initial,
          difficulty: metadata.level,
          target_rating: metadata.target,
        };
        if (sourceReference.trim() !== (existing.source_reference ?? "")) {
          patch.source_reference = sourceReference.trim() || null;
        }
        if (JSON.stringify(hintJson) !== JSON.stringify(existing.hint_json)) {
          patch.hint_json = hintJson;
        }
        if (!meaningLocked) {
          if (JSON.stringify(finalAnswer) !== JSON.stringify(existing.answer_json)) {
            patch.answer_json = finalAnswer;
          }
          if (showBoard && fen !== existing.fen) patch.fen = fen;
          if (JSON.stringify(finalPosition) !== JSON.stringify(existing.position_json)) {
            patch.position_json = finalPosition;
          }
        }
        row = await adminApi.updatePuzzle(existing.id, patch);
      }
      navigate(`/admin/puzzles/${row.id}`);
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!existing || !canDeleteDraft) return;
    if (!window.confirm(t("admin.editor.deleteConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await adminApi.deletePuzzle(existing.id);
      navigate("/admin/puzzles");
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>;
  }
  if (failed) {
    return (
      <div className="py-8 text-center">
        <p className="text-stone-500">{t("common.error")}</p>
        <div className="mx-auto mt-3 max-w-xs">
          <Button onClick={() => window.location.reload()} className="w-full">{t("common.retry")}</Button>
        </div>
      </div>
    );
  }

  const visibilityText = existing?.is_published
    ? t("admin.statusPublished")
    : existing?.is_archived
      ? t("admin.statusArchived")
      : t("admin.editor.saveDraftNote");
  const positionContract = contract
    ? {
        ...contract,
        position_fields: contract.position_fields.filter((field) => !AUTO_POSITION_FIELDS.has(field.name)),
      }
    : null;
  const selectedExerciseTitle = exercises.find((item) => item.slug === slug)?.title_fa ?? "";

  return (
    <>
      <PageHeader
        title={isNew ? t("admin.editor.addNew") : t("admin.editPuzzle")}
         subtitle={selectedExerciseTitle || t("admin.workspace")}
      />
      {notice ? <p className="mb-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}
      <div className="flex flex-col gap-2">
        <Card>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs text-stone-500">{t("admin.lifecycleState")}</p>
              <p className="mt-1 font-black">{statusLabel(existing?.status ?? "draft")}</p>
              <p className="mt-1 text-xs text-stone-500">{visibilityText}</p>
            </div>
            {existing ? (
              <span className="text-left text-xs text-stone-500" dir="ltr">#{faNum(existing.id)}</span>
            ) : null}
          </div>
          {existing && !meaningLocked && ["validated", "reviewed", "approved"].includes(existing.status) ? (
            <p className="mt-2 text-xs font-bold text-amber-700">{t("admin.editDemotionNote")}</p>
          ) : null}
          {contract ? (
            <div className="mt-3 border-t border-stone-100 pt-3 text-xs text-stone-500">
              <p>
                {t("admin.answerType")}: <b dir="ltr">{contract.answer_type}</b> ·{" "}
                {t("admin.answerAttemptField")}: <b dir="ltr">{contract.attempt_field}</b>
              </p>
              {!contract.validator_registered ? (
                <p className="mt-1 font-bold text-red-600">{t("admin.exerciseNotImplemented")}</p>
              ) : null}
            </div>
          ) : null}
        </Card>

        <Card>
          <h2 className="font-black">{t("admin.editor.sourceReference")}</h2>
          <input
            aria-label={t("admin.editor.sourceReference")}
            dir="ltr"
            value={sourceReference}
            disabled={busy || metadataLocked}
            onChange={(event) => setSourceReference(event.target.value)}
            className="mt-2 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm"
          />
          <h2 className="mt-4 font-black">{t("admin.editor.hintData")}</h2>
          <StructuredAnswerEditor
            answer={hintJson}
            onChange={(next) => {
              setHintJson(next);
              setPreview(null);
            }}
            disabled={busy || metadataLocked}
          />
        </Card>

        <Card>
          <label className="text-sm font-bold" htmlFor="editor-exercise">
            {t("admin.label.exercise")}
          </label>
          <select
            id="editor-exercise"
            value={slug}
            disabled={!isNew || busy}
            onChange={(event) => {
              setSlug(event.target.value);
              setAnswer({});
              setPositionJson({});
              setHintJson({});
              setFen(START_FEN);
              setDifficulty("");
              setRating("1200");
              setTargetRating("");
              setSourceReference("");
              setPrompt("");
              setExplanation("");
              setPreview(null);
            }}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
          >
            <option value="">—</option>
            {exercises.map((exercise) => (
              <option key={exercise.slug} value={exercise.slug}>
                {exercise.title_fa} · {exercise.slug}
              </option>
            ))}
          </select>
          {!isNew ? <p className="mt-1 text-xs text-stone-500">{t("admin.editor.exerciseLocked")}</p> : null}
        </Card>

        {showBoard ? (
          <Card>
            <h2 className="font-black">{t("admin.position")}</h2>
            <div className="mt-2">
              <BoardEditor fen={fen} onChange={setFen} disabled={busy || meaningLocked} />
            </div>
          </Card>
        ) : null}

        {positionContract && positionContract.position_fields.length > 0 ? (
          <Card>
            <h2 className="font-black">{t("admin.editor.positionData")}</h2>
            <div className="mt-2">
              <PositionDataEditor
                contract={positionContract}
                value={positionJson}
                onChange={(next) => {
                  setPositionJson(next);
                  setPreview(null);
                }}
                disabled={busy || meaningLocked}
              />
            </div>
          </Card>
        ) : null}

        <Card>
          <h2 className="font-black">{t("admin.expectedAnswer")}</h2>
          {contract ? (
            <div className="mt-2">
              <AnswerEditor
                contract={contract}
                answer={answer}
                onChange={(next) => {
                  setAnswer(next);
                  setPreview(null);
                }}
                disabled={busy || meaningLocked}
              />
            </div>
          ) : (
            <p className="mt-1 text-sm text-stone-500">{t("admin.empty")}</p>
          )}
        </Card>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2">
          <Card>
            <h2 className="font-black">{t("admin.difficulty")}</h2>
            <div className="mt-2 grid grid-cols-5 gap-1" dir="ltr">
              {[1, 2, 3, 4, 5].map((level) => (
                <button
                  key={level}
                  type="button"
                  disabled={busy || metadataLocked}
                  onClick={() => setDifficulty(difficulty === String(level) ? "" : String(level))}
                  className={`min-h-[44px] rounded-xl border font-black ${
                    difficulty === String(level)
                      ? "border-violet-700 bg-violet-700 text-white"
                      : "border-stone-200 bg-white"
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
            <p className="mt-1 text-xs text-stone-500">{t("admin.difficultyHint")}</p>
          </Card>
          <Card>
            <h2 className="font-black">{t("admin.editor.targetRating")}</h2>
            <input
              aria-label={t("admin.editor.targetRating")}
              dir="ltr"
              inputMode="decimal"
              value={targetRating}
              disabled={busy || metadataLocked}
              onChange={(event) => setTargetRating(event.target.value)}
              className="mt-2 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm"
            />
            <p className="mt-1 text-xs text-stone-500">{t("admin.ratingHint")}</p>
            <label className="mt-3 block text-sm font-bold" htmlFor="editor-rating">
              {t("admin.rating")}
            </label>
            <input
              id="editor-rating"
              dir="ltr"
              inputMode="decimal"
              value={rating}
              disabled={busy || metadataLocked}
              onChange={(event) => setRating(event.target.value)}
              className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm"
            />
            <p className="mt-1 text-xs text-stone-500">{t("admin.ratingHint")}</p>
          </Card>
        </div>

        <Card>
          <label className="text-sm font-bold" htmlFor="editor-prompt">
            {t("admin.promptFa")}
          </label>
          <input
            id="editor-prompt"
            value={prompt}
            disabled={busy || metadataLocked}
            onChange={(event) => setPrompt(event.target.value)}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
          <label className="mt-3 block text-sm font-bold" htmlFor="editor-explanation">
            {t("admin.explanation")}
          </label>
          <textarea
            id="editor-explanation"
            value={explanation}
            disabled={busy || metadataLocked}
            onChange={(event) => setExplanation(event.target.value)}
            rows={3}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 py-2 text-sm"
          />
        </Card>

        {existing ? (
          <Card>
            <h2 className="font-black">{t("admin.label.source")}</h2>
            <dl className="mt-2 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-stone-500">{t("admin.source")}</dt>
                <dd>{sourceLabel(existing.source)}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.editor.sourceReference")}</dt>
                <dd className="break-all" dir="ltr">{sourceReference || "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.runDetail")}</dt>
                <dd dir="ltr">{existing.generator_run_id ?? "—"}</dd>
              </div>
              <div>
                <dt className="text-xs text-stone-500">{t("admin.editor.positionData")}</dt>
                <dd>{faNum(Object.keys(positionJson).length)}</dd>
              </div>
            </dl>
          </Card>
        ) : null}

        <Card>
          <h2 className="font-black">{t("admin.validationState")}</h2>
          <p className="mt-1 text-xs text-stone-500">{t("admin.editor.previewNote")}</p>
          <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Button
              disabled={busy || !slug || !contract?.validator_registered}
              variant="secondary"
              onClick={() => void onValidate()}
            >
              {t("admin.validateBeforeSave")}
            </Button>
            <Button
              disabled={busy || metadataLocked || !slug || !contract?.validator_registered}
              onClick={() => void onSave()}
            >
              {isNew ? t("admin.saveDraft") : t("admin.saveChanges")}
            </Button>
          </div>
          {preview ? (
            <div className={`mt-2 text-sm font-bold ${preview.ok ? "text-green-700" : "text-red-600"}`}>
              <p>{preview.ok ? t("admin.validationPassed") : t("admin.validationFailed")}</p>
              {preview.errors.length > 0 ? (
                <p className="mt-1 text-xs">
                  {t("admin.editor.validationErrorsCount").replace("{count}", faNum(preview.errors.length))}
                </p>
              ) : null}
            </div>
          ) : null}
          <p className="mt-2 text-xs text-stone-500">{t("admin.editor.saveDraftNote")}</p>
        </Card>

        {canDeleteDraft ? (
          <Card>
            <Button disabled={busy} variant="secondary" onClick={() => void onDelete()} className="w-full">
              {t("admin.editor.deleteDraft")}
            </Button>
            <p className="mt-1 text-xs text-stone-500">{t("admin.editor.deleteConfirm")}</p>
          </Card>
        ) : existing ? (
          <Card>
            <p className="text-sm text-stone-500">{t("admin.editor.deleteBlocked")}</p>
          </Card>
        ) : null}

        <Card>
          <h2 className="font-black">{t("admin.puzzlePreview")}</h2>
          {prompt ? <p className="mt-2">{prompt}</p> : null}
          {showBoard && fen ? (
            <div dir="ltr" className="mx-auto mt-2 max-w-sm">
              <ChessBoard pieces={fenToPieces(fen)} disabled />
            </div>
          ) : null}
          {contract ? (
            <p className="mt-2 break-all font-mono text-xs text-stone-500" dir="ltr">
              {answerSummary(buildAnswer())}
            </p>
          ) : null}
        </Card>
      </div>
    </>
  );
}
