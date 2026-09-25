import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { adminApi } from "../api/client";
import type { AdminExercise, AdminPuzzle } from "../api/types";
import { ChessBoard } from "../components/chess/ChessBoard";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { fenToPieces } from "../lib/fen";
import { faNum } from "../lib/playerDisplay";

const PAGE_SIZE = 20;
const MAX_SELECTION = 50;
const STATUSES = ["draft", "validated", "reviewed", "approved", "published", "quarantined", "rejected", "retired"];
const MEANING_LOCKED = new Set(["published", "retired", "archived", "rejected", "quarantined"]);
const DESTRUCTIVE_ACTIONS = new Set(["quarantine", "reject", "retire"]);
type BulkAction = "validate" | "approve" | "publish" | "quarantine" | "reject" | "retire";

function statusLabel(status: string): string {
  if (status === "draft") return t("admin.statusDraft");
  if (status === "validated") return t("admin.statusValidated");
  if (status === "reviewed") return t("admin.statusReviewed");
  if (status === "approved") return t("admin.statusApproved");
  if (status === "published") return t("admin.statusPublished");
  if (status === "quarantined") return t("admin.status.quarantined");
  if (status === "rejected") return t("admin.status.rejected");
  if (status === "retired" || status === "archived") return t("admin.status.retired");
  return t("admin.unknown");
}

function sourceLabel(source: string): string {
  if (source === "manual") return t("admin.sourceManual");
  if (source === "generated") return t("admin.sourceGenerated");
  if (source === "imported") return t("admin.sourceImported");
  return t("admin.unknown");
}

function formatDate(value: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fa-IR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function AdminPuzzlesPage() {
  const [searchParams] = useSearchParams();
  const [rows, setRows] = useState<AdminPuzzle[]>([]);
  const [exercises, setExercises] = useState<AdminExercise[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [exercise, setExercise] = useState(searchParams.get("exercise") ?? "");
  const [status, setStatus] = useState(searchParams.get("status") ?? "");
  const [difficulty, setDifficulty] = useState("");
  const [source, setSource] = useState("");
  const [search, setSearch] = useState("");
  const [ratingMin, setRatingMin] = useState("");
  const [ratingMax, setRatingMax] = useState("");
  const [sort, setSort] = useState("id");
  const [order, setOrder] = useState("desc");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<number[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [reason, setReason] = useState("");
  const requestId = useRef(0);

  useEffect(() => {
    if (typeof adminApi.exercises !== "function") return;
    Promise.resolve(adminApi.exercises()).then((items) => setExercises(items ?? [])).catch(() => setExercises([]));
  }, []);

  const load = useCallback(async () => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
    setLoading(true);
    setFailed(false);
    const params = {
      exercise: exercise || undefined,
      status: status || undefined,
      difficulty: difficulty ? Number(difficulty) : undefined,
      source: source || undefined,
      search: search || undefined,
      rating_min: ratingMin ? Number(ratingMin) : undefined,
      rating_max: ratingMax ? Number(ratingMax) : undefined,
      sort,
      order,
      page,
      page_size: PAGE_SIZE,
    };
    try {
      const loader = typeof adminApi.puzzlesPage === "function" ? adminApi.puzzlesPage : adminApi.puzzles;
      const response = await loader(params);
      if (requestId.current !== currentRequest) return;
      if (Array.isArray(response)) {
        setRows(response);
        setTotal(response.length);
      } else {
        setRows(response.items);
        setTotal(response.total);
      }
    } catch {
      if (requestId.current === currentRequest) setFailed(true);
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [difficulty, exercise, order, page, ratingMax, ratingMin, search, sort, source, status]);

  useEffect(() => {
    void load();
  }, [load]);

  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  useEffect(() => {
    if (page > pages) setPage(pages);
  }, [page, pages]);

  function resetContext() {
    setPage(1);
    setSelected([]);
    setNotice("");
  }

  function toggle(id: number) {
    setSelected((current) => {
      if (current.includes(id)) return current.filter((item) => item !== id);
      if (current.length >= MAX_SELECTION) return current;
      return [...current, id];
    });
  }

  function togglePage() {
    const ids = rows.map((row) => row.id);
    const allSelected = ids.length > 0 && ids.every((id) => selected.includes(id));
    setSelected((current) => {
      if (allSelected) return current.filter((id) => !ids.includes(id));
      const next = new Set(current);
      for (const id of ids) {
        if (next.size >= MAX_SELECTION) break;
        next.add(id);
      }
      return [...next];
    });
  }

  async function bulk(action: BulkAction) {
    if (selected.length === 0) return;
    const cleanReason = reason.trim();
    if (DESTRUCTIVE_ACTIONS.has(action) && !cleanReason) return;
    if ((DESTRUCTIVE_ACTIONS.has(action) || action === "publish") && !window.confirm(t("admin.bulkConfirm"))) {
      return;
    }
    const ids = [...selected];
    setBusy(true);
    setNotice("");
    try {
      const result = await adminApi.bulkPuzzles({
        puzzle_ids: ids,
        action,
        reason: cleanReason,
      });
      const succeeded = new Set(result.succeeded);
      setSelected((current) => current.filter((id) => !succeeded.has(id)));
      if (result.failed.length > 0) {
        setNotice(
           `${t("admin.bulkPartial")} ${result.failed
             .map((failure) => `#${faNum(failure.id)}: ${t("admin.operationFailed")}`)
             .join(" · ")}`,
        );
      } else if (DESTRUCTIVE_ACTIONS.has(action)) {
        setReason("");
      }
      await load();
    } catch {
      setNotice(t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  const allPageSelected = rows.length > 0 && rows.every((row) => selected.includes(row.id));
  const addPath = exercise ? `/admin/puzzles/new?exercise=${encodeURIComponent(exercise)}` : "/admin/puzzles/new";

  return (
    <>
      <PageHeader title={t("admin.puzzles")} subtitle={t("admin.subtitle")} />
      <Card>
        <p className="text-xs text-stone-500">{t("admin.lifecycleHint")}</p>
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {t("admin.label.exercise")}
            <select
              value={exercise}
              onChange={(event) => {
                setExercise(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            >
              <option value="">{t("admin.all")}</option>
              {exercises.map((item) => (
                <option key={item.slug} value={item.slug}>{item.title_fa} · {item.slug}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {t("admin.label.status")}
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            >
              <option value="">{t("admin.allStatuses")}</option>
              {STATUSES.map((value) => (
                 <option key={value} value={value} aria-label={statusLabel(value)}>
                   {statusLabel(value)}
                 </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {t("admin.label.difficulty")}
            <select
              value={difficulty}
              onChange={(event) => {
                setDifficulty(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            >
              <option value="">{t("admin.allDifficulties")}</option>
              {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{faNum(value)}</option>)}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {t("admin.label.source")}
            <select
              value={source}
              onChange={(event) => {
                setSource(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            >
              <option value="">{t("admin.allSources")}</option>
              <option value="manual">{t("admin.sourceManual")}</option>
              <option value="generated">{t("admin.sourceGenerated")}</option>
              <option value="imported">{t("admin.sourceImported")}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500 sm:col-span-2">
            {t("admin.searchPuzzles")}
             <input
               value={search}
               placeholder={t("admin.searchPuzzles")}
              onChange={(event) => {
                setSearch(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {`${t("admin.ratingRange")} ${t("admin.label.start")}`}
            <input
              value={ratingMin}
              onChange={(event) => {
                setRatingMin(event.target.value);
                resetContext();
              }}
              inputMode="decimal"
              dir="ltr"
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {`${t("admin.ratingRange")} ${t("admin.label.end")}`}
            <input
              value={ratingMax}
              onChange={(event) => {
                setRatingMax(event.target.value);
                resetContext();
              }}
              inputMode="decimal"
              dir="ltr"
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 font-mono text-sm font-normal"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {t("admin.sortBy")}
            <select
              value={sort}
              onChange={(event) => {
                setSort(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            >
              <option value="id">{t("admin.sortId")}</option>
              <option value="created_at">{t("admin.sortCreated")}</option>
              <option value="initial_rating">{t("admin.sortRating")}</option>
              <option value="difficulty">{t("admin.sortDifficulty")}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs font-bold text-stone-500">
            {t("admin.label.result")}
            <select
              value={order}
              onChange={(event) => {
                setOrder(event.target.value);
                resetContext();
              }}
              className="min-h-[44px] rounded-xl border border-stone-200 bg-white px-3 text-sm font-normal text-stone-900"
            >
              <option value="desc">{t("admin.orderDesc")}</option>
              <option value="asc">{t("admin.orderAsc")}</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            to={addPath}
            className="inline-flex min-h-[44px] items-center rounded-xl bg-violet-700 px-4 text-sm font-bold text-white"
          >
            {t("admin.editor.addNew")}
          </Link>
          <Link
            to="/admin/content-health"
            className="inline-flex min-h-[44px] items-center px-2 text-sm font-bold text-violet-700"
          >
            {t("admin.contentHealth")}
          </Link>
          <span className="inline-flex min-h-[44px] items-center text-sm text-stone-500">
            {t("admin.table.total")}: {faNum(total)}
          </span>
        </div>
      </Card>

      {selected.length > 0 ? (
        <Card className="mt-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-bold">{t("admin.bulkSelected")}: {faNum(selected.length)}</p>
            <button type="button" onClick={() => setSelected([])} className="min-h-[44px] px-2 text-sm font-bold text-violet-700">
              {t("admin.selection.clear")}
            </button>
          </div>
          <p className="mt-1 text-xs text-stone-500">{t("admin.selection.limit")}</p>
          <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-6">
            <Button disabled={busy} variant="secondary" onClick={() => void bulk("validate")}>{t("admin.bulkValidate")}</Button>
            <Button disabled={busy} variant="secondary" onClick={() => void bulk("approve")}>{t("admin.bulkApprove")}</Button>
            <Button disabled={busy} variant="secondary" onClick={() => void bulk("publish")}>{t("admin.bulkPublish")}</Button>
            <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void bulk("quarantine")}>{t("admin.bulkQuarantine")}</Button>
            <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void bulk("reject")}>{t("admin.reject")}</Button>
            <Button disabled={busy || !reason.trim()} variant="secondary" onClick={() => void bulk("retire")}>{t("admin.bulkRetire")}</Button>
          </div>
          <label className="mt-2 block text-sm font-bold" htmlFor="bulk-reason">{t("admin.label.reason")}</label>
          <input
            id="bulk-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder={t("admin.label.reason")}
            className="mt-1 min-h-[44px] w-full rounded-xl border border-stone-200 bg-white px-3 text-sm"
          />
        </Card>
      ) : null}

      {notice ? <p className="mt-2 text-center text-sm font-bold text-red-600">{notice}</p> : null}
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <div className="py-8 text-center">
          <p className="text-stone-500">{t("common.error")}</p>
          <div className="mx-auto mt-3 max-w-xs"><Button onClick={() => void load()} className="w-full">{t("common.retry")}</Button></div>
        </div>
      ) : rows.length === 0 ? (
        <Card><p className="text-center text-stone-500">{t("admin.empty")}</p></Card>
      ) : (
        <Card className="mt-3 overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1180px] border-collapse text-right text-sm">
              <thead className="bg-stone-50 text-xs text-stone-600">
                <tr>
                  <th className="p-3">
                    <button type="button" onClick={togglePage} className="min-h-[44px] font-bold text-violet-700">
                      {allPageSelected ? t("admin.selection.clear") : t("admin.selection.all")}
                    </button>
                  </th>
                  <th className="p-3">{t("admin.table.puzzleId")}</th>
                  <th className="p-3">{t("admin.table.board")}</th>
                  <th className="p-3">{t("admin.label.exercise")}</th>
                  <th className="p-3">{t("admin.label.difficulty")}</th>
                  <th className="p-3">{t("admin.label.rating")}</th>
                  <th className="p-3">{t("admin.label.status")}</th>
                  <th className="p-3">{t("admin.label.source")}</th>
                   <th className="p-3">{t("admin.label.created")}</th>
                   <th className="p-3">{t("admin.attempts")}</th>
                   <th className="p-3">{t("admin.label.actions")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((puzzle) => (
                  <tr key={puzzle.id} className="border-t border-stone-100 align-middle hover:bg-stone-50">
                    <td className="p-3">
                      <input
                        type="checkbox"
                        checked={selected.includes(puzzle.id)}
                        onChange={() => toggle(puzzle.id)}
                        disabled={!selected.includes(puzzle.id) && selected.length >= MAX_SELECTION}
                        aria-label={`${t("admin.table.puzzleId")} ${puzzle.id}`}
                        className="h-6 w-6"
                      />
                    </td>
                    <td className="p-3">
                      <span className="font-black" dir="ltr">#{puzzle.id}</span>
                      {puzzle.prompt_fa ? <p className="mt-1 max-w-[180px] text-xs text-stone-500">{puzzle.prompt_fa}</p> : null}
                    </td>
                    <td className="p-3">
                      {puzzle.fen ? (
                        <div dir="ltr" className="w-20"><ChessBoard pieces={fenToPieces(puzzle.fen)} disabled /></div>
                      ) : <span className="text-stone-400">—</span>}
                    </td>
                    <td className="p-3">
                      <span className="font-bold">{exercises.find((item) => item.slug === puzzle.exercise_slug)?.title_fa ?? puzzle.exercise_slug}</span>
                      <span className="mt-1 block text-xs text-stone-500" dir="ltr">{puzzle.exercise_slug}</span>
                    </td>
                    <td className="p-3 font-mono" dir="ltr">{puzzle.difficulty ?? "—"}</td>
                    <td className="p-3 font-mono" dir="ltr">{faNum(puzzle.initial_rating)}</td>
                    <td className="p-3">
                       <Badge>{statusLabel(puzzle.status)}</Badge>
                    </td>
                    <td className="p-3">
                      <span>{sourceLabel(puzzle.source)}</span>
                      {puzzle.source_reference ? (
                        <span className="mt-1 block max-w-[140px] truncate text-xs text-stone-500" dir="ltr">{puzzle.source_reference}</span>
                      ) : null}
                    </td>
                     <td className="p-3 text-xs text-stone-500" dir="ltr">{formatDate(puzzle.created_at)}</td>
                     <td className="p-3 font-mono" dir="ltr">{faNum(puzzle.usage_attempts ?? 0)}</td>
                     <td className="p-3">
                      <div className="flex min-w-[120px] flex-col items-start">
                        <Link to={`/admin/puzzles/${puzzle.id}`} className="inline-flex min-h-[44px] items-center text-sm font-bold text-violet-700">
                          {t("admin.openPuzzle")}
                        </Link>
                        {!MEANING_LOCKED.has(puzzle.status) ? (
                          <Link to={`/admin/puzzles/${puzzle.id}/edit`} className="inline-flex min-h-[44px] items-center text-sm font-bold text-violet-700">
                            {t("admin.editPuzzle")}
                          </Link>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <div className="mt-3 flex items-center justify-between gap-2">
        <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
          {t("admin.pagination.previous")}
        </Button>
        <span className="text-center text-sm font-bold">
          {t("admin.pagination.summary")
            .replace("{page}", faNum(page))
            .replace("{pages}", faNum(pages))
            .replace("{total}", faNum(total))}
        </span>
        <Button variant="secondary" disabled={page >= pages} onClick={() => setPage((current) => Math.min(pages, current + 1))}>
          {t("admin.pagination.next")}
        </Button>
      </div>
    </>
  );
}
