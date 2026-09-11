import { useCallback, useEffect, useState } from "react";
import { apiDetail, coachApi, parentApi } from "../api/client";
import type {
  AchievementsResponse,
  Assignment,
  GamificationSummary,
  HistoryAttempt,
  PlayerAnalytics,
  ProgressSummary,
  RatingsResponse,
  RelatedStudent,
} from "../api/types";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageHeader } from "../components/ui/PageHeader";
import { t } from "../i18n";
import { faDate, faNum, faPercent } from "../lib/playerDisplay";

type Kind = "coach" | "parent";

interface Detail {
  progress: ProgressSummary | null;
  attempts: HistoryAttempt[];
  ratings: RatingsResponse | null;
  gamification: GamificationSummary | null;
  achievements: AchievementsResponse | null;
  analytics: PlayerAnalytics | null;
  assignments: Assignment[];
}

// Related-student views for coaches and parents. The two kinds share
// read shapes but never share authorization: each kind calls its own
// endpoints, and the server filters by the matching relationship kind.
// Assignment management exists for coaches only; parents see assignments
// read-only. Guards here are UX only.
export function MentorStudentsPage({ kind }: { kind: Kind }) {
  const reads = kind === "coach" ? coachApi : parentApi;
  const [students, setStudents] = useState<RelatedStudent[]>([]);
  const [selected, setSelected] = useState<RelatedStudent | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [detailFailed, setDetailFailed] = useState(false);
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [exercise, setExercise] = useState("");
  const [note, setNote] = useState("");

  const isCoach = kind === "coach";
  const title = isCoach ? t("coach.title") : t("parent.title");
  const subtitle = isCoach ? t("coach.subtitle") : t("parent.subtitle");
  const empty = isCoach ? t("coach.empty") : t("parent.empty");

  const load = useCallback(() => {
    setLoading(true);
    setFailed(false);
    const list = isCoach ? coachApi.students() : parentApi.children();
    list
      .then((res) => {
        setStudents(res);
        setLoading(false);
      })
      .catch(() => {
        setFailed(true);
        setLoading(false);
      });
  }, [isCoach]);

  useEffect(() => {
    load();
  }, [load]);

  async function openDetail(student: RelatedStudent) {
    setSelected(student);
    setDetail(null);
    setDetailFailed(false);
    setNotice("");
    try {
      const [progress, attempts, ratings, gamification, achievements, analytics] = await Promise.all([
        reads.progress(student.id),
        reads.attempts(student.id),
        reads.ratings(student.id),
        reads.gamification(student.id),
        reads.achievements(student.id),
        reads.analytics(student.id, { period: "30d" }),
      ]);
      const assignments = isCoach
        ? await coachApi.assignments(student.id)
        : await parentApi.assignments(student.id);
      setDetail({ progress, attempts: attempts.slice(0, 5), ratings, gamification, achievements, analytics, assignments });
    } catch {
      setDetailFailed(true);
    }
  }

  async function createAssignment() {
    if (!selected || !exercise.trim() || busy) return;
    setBusy(true);
    setNotice("");
    try {
      await coachApi.createAssignment({
        student_id: selected.id,
        exercise_slug: exercise.trim(),
        note: note.trim(),
      });
      setExercise("");
      setNote("");
      await openDetail(selected);
      load();
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  async function setAssignmentStatus(id: number, status: string) {
    if (!selected || busy) return;
    if (status === "cancelled" && !window.confirm(t("rel.revokeConfirm"))) return;
    setBusy(true);
    setNotice("");
    try {
      await coachApi.updateAssignment(id, status);
      await openDetail(selected);
    } catch (e) {
      setNotice(apiDetail(e) || t("common.error"));
    } finally {
      setBusy(false);
    }
  }

  function assignmentLabel(status: string): string {
    if (status === "completed") return t("assign.completed");
    if (status === "cancelled") return t("assign.cancelled");
    return t("assign.assigned");
  }

  if (selected !== null && detailFailed) {
    return (
      <div>
        <Button variant="ghost" onClick={() => setSelected(null)}>
          {t("common.back")}
        </Button>
        <Card>
          <p className="text-center font-bold text-stone-500">{t("common.error")}</p>
        </Card>
      </div>
    );
  }

  if (selected !== null && detail !== null) {
    const unlocked = detail.achievements?.items.filter((a) => a.unlocked).length ?? 0;
    return (
      <div>
        <Button variant="ghost" onClick={() => setSelected(null)}>
          {t("common.back")}
        </Button>
        <PageHeader title={selected.display_name || selected.username} subtitle={isCoach ? t("coach.detail") : t("parent.detail")} />
        <div className="flex flex-col gap-3">
          <Card>
            <h2 className="mb-2 text-lg font-black text-stone-900">{t("player.totalAttempts")}</h2>
            <p className="text-2xl font-black text-violet-700">{faNum(detail.progress?.attempts ?? 0)}</p>
            <p className="mt-1 text-sm text-stone-500">
              {t("player.accuracy")}: {faPercent(detail.progress?.accuracy ?? 0)} · {t("player.correctCount")}:{" "}
              {faNum(detail.progress?.correct ?? 0)}
            </p>
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-black text-stone-900">{t("game.title")}</h2>
            <p className="text-sm text-stone-600">
              {t("game.level")} {faNum(detail.gamification?.xp.level ?? 1)} · {t("game.xp")}{" "}
              {faNum(detail.gamification?.xp.total ?? 0)} · {t("game.streak")}{" "}
              {faNum(detail.gamification?.streak.current ?? 0)} · {t("game.achievements")}{" "}
              {faNum(unlocked)}
            </p>
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-black text-stone-900">{t("rating.title")}</h2>
            {detail.ratings && detail.ratings.items.length > 0 ? (
              <ul className="flex flex-col gap-1">
                {detail.ratings.items.map((r) => (
                  <li key={r.exercise} className="text-sm text-stone-600" dir="ltr">
                    {r.exercise}: <strong>{faNum(Math.round(r.rating))}</strong>
                    {r.provisional ? <Badge> {t("rating.provisional")}</Badge> : null}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-stone-500">{t("rating.empty")}</p>
            )}
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-black text-stone-900">{t("analytics.title")}</h2>
            <p className="text-sm text-stone-600">
              {t("analytics.activeDays")}: {faNum(detail.analytics?.totals.active_days ?? 0)} ·{" "}
              {t("player.accuracy")}: {faPercent(detail.analytics?.totals.accuracy ?? 0)} ·{" "}
              {t("analytics.xpEarned")}: {faNum(detail.analytics?.xp.earned_in_period ?? 0)}
            </p>
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-black text-stone-900">
              {isCoach ? t("coach.recentAttempts") : t("player.recentActivity")}
            </h2>
            {detail.attempts.length === 0 ? (
              <p className="text-sm text-stone-500">{t("player.noActivity")}</p>
            ) : (
              <ul className="flex flex-col gap-1">
                {detail.attempts.map((a) => (
                  <li key={a.id} className="text-sm text-stone-600" dir="ltr">
                    {a.exercise_slug} · {a.mode} · {a.result} · {faDate(a.created_at)}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          <Card>
            <h2 className="mb-2 text-lg font-black text-stone-900">{t("assign.title")}</h2>
            {detail.assignments.length === 0 ? (
              <p className="text-sm text-stone-500">{t("assign.empty")}</p>
            ) : (
              <ul className="flex flex-col gap-2">
                {detail.assignments.map((a) => (
                  <li key={a.id} className="rounded-2xl bg-stone-50 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-bold text-stone-800" dir="ltr">
                        {a.exercise_slug}
                      </p>
                      <Badge>{assignmentLabel(a.status)}</Badge>
                    </div>
                    {a.note ? <p className="mt-1 text-sm text-stone-600">{a.note}</p> : null}
                    {isCoach && a.status === "assigned" ? (
                      <div className="mt-2 flex gap-2">
                        <Button variant="secondary" onClick={() => setAssignmentStatus(a.id, "completed")} disabled={busy}>
                          {t("assign.complete")}
                        </Button>
                        <Button variant="ghost" onClick={() => setAssignmentStatus(a.id, "cancelled")} disabled={busy}>
                          {t("assign.cancel")}
                        </Button>
                      </div>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
            {isCoach ? (
              <div className="mt-3 border-t border-stone-100 pt-3">
                <label className="mb-1 block text-sm font-bold text-stone-600" htmlFor="assign-exercise">
                  {t("assign.exercise")}
                </label>
                <input
                  id="assign-exercise"
                  dir="ltr"
                  value={exercise}
                  onChange={(e) => setExercise(e.target.value)}
                  placeholder="piece-recognition"
                  className="mb-2 flex min-h-[44px] w-full items-center rounded-2xl border border-stone-200 bg-white px-3 text-base"
                />
                <label className="mb-1 block text-sm font-bold text-stone-600" htmlFor="assign-note">
                  {t("assign.note")}
                </label>
                <input
                  id="assign-note"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder={t("assign.notePlaceholder")}
                  className="mb-2 flex min-h-[44px] w-full items-center rounded-2xl border border-stone-200 bg-white px-3 text-base"
                />
                <Button onClick={createAssignment} disabled={busy || !exercise.trim()}>
                  {t("assign.create")}
                </Button>
                {notice ? <p className="mt-2 text-sm font-bold text-stone-600">{notice}</p> : null}
              </div>
            ) : null}
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div>
      <PageHeader title={title} subtitle={subtitle} />
      {loading ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : failed ? (
        <Card>
          <p className="text-center font-bold text-stone-500">{t("common.error")}</p>
          <div className="mt-3 text-center">
            <Button variant="secondary" onClick={load}>
              {t("common.retry")}
            </Button>
          </div>
        </Card>
      ) : students.length === 0 ? (
        <Card>
          <p className="text-center font-bold text-stone-500">{empty}</p>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {students.map((student) => (
            <Card key={student.id}>
              <button
                type="button"
                onClick={() => openDetail(student)}
                className="flex min-h-[44px] w-full items-center justify-between gap-2 text-right"
              >
                <span className="font-black text-stone-900">{student.display_name || student.username}</span>
                <span className="text-sm text-stone-500" dir="ltr">
                  {student.username}
                </span>
              </button>
            </Card>
          ))}
        </div>
      )}
      {selected !== null && detail === null && !detailFailed ? (
        <p className="py-8 text-center text-stone-500">{t("common.loading")}</p>
      ) : null}
    </div>
  );
}

export function CoachStudentsPage() {
  return <MentorStudentsPage kind="coach" />;
}

export function ParentChildrenPage() {
  return <MentorStudentsPage kind="parent" />;
}
