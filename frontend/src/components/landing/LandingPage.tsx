import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { ChessPiece } from "../chess/ChessPiece";
import { t } from "../../i18n";
import { captureAttribution } from "../../lib/attribution";
import { faNum } from "../../lib/playerDisplay";
import "./landing.css";

// Anonymous marketing landing. Authenticated sessions never reach this
// component (HomePage routes them to their role dashboards). No exercise
// catalog here by design — the catalog lives at /exercises.
export function LandingPage() {
  useRevealOnScroll();
  const location = useLocation();
  // Persist first-touch attribution (survives into registration).
  useEffect(() => {
    captureAttribution(location.search, `${location.pathname}${location.search}`);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="mc-landing">
      <LandingAnchors />
      <LandingHero />
      <ContrastSection />
      <WhySection />
      <FeaturesSection />
      <HowSection />
      <PersonalSection />
      <ParentSection />
      <ChildSection />
      <GuideSection />
      <FreeSection />
      <FinalCta />
      <LandingFooter />
    </div>
  );
}

// One-shot IntersectionObserver: sections fade up on first visibility.
function useRevealOnScroll() {
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      document.querySelectorAll(".mc-reveal").forEach((el) => el.classList.add("is-visible"));
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.12 },
    );
    document.querySelectorAll(".mc-reveal").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);
}

function SectionShell({
  id,
  eyebrow,
  title,
  subtitle,
  children,
  tone = "plain",
}: {
  id: string;
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  tone?: "plain" | "soft";
}) {
  return (
    <section
      id={id}
      aria-labelledby={`${id}-title`}
      className={`px-4 py-14 md:py-20 ${tone === "soft" ? "bg-white" : ""}`}
    >
      <div className="mc-reveal mx-auto max-w-5xl">
        <p className="text-sm font-black text-violet-600">{eyebrow}</p>
        <h2 id={`${id}-title`} className="mt-2 text-2xl font-black text-stone-900 md:text-3xl">
          {title}
        </h2>
        {subtitle ? <p className="mt-2 max-w-2xl text-base text-stone-500">{subtitle}</p> : null}
        <div className="mt-8">{children}</div>
      </div>
    </section>
  );
}

// In-page anchor shortcuts. Horizontally scrollable on phones — no burger
// menu needed for four links.
function LandingAnchors() {
  const items: Array<[string, string]> = [
    ["#why", t("landing.nav.why")],
    ["#features", t("landing.nav.features")],
    ["#how", t("landing.nav.how")],
    ["#guide", t("landing.nav.guide")],
  ];
  return (
    <nav aria-label={t("app.name")} className="px-4 pt-2">
      <div className="mx-auto flex max-w-5xl gap-2 overflow-x-auto pb-1">
        {items.map(([href, label]) => (
          <a
            key={href}
            href={href}
            className="flex min-h-[44px] shrink-0 items-center rounded-full bg-white px-4 text-sm font-bold text-violet-700 shadow-sm shadow-violet-100"
          >
            {label}
          </a>
        ))}
      </div>
    </nav>
  );
}

function LandingHero() {
  return (
    <section aria-labelledby="landing-hero-title" className="px-4 pb-10 pt-6 md:pt-12">
      <div className="mx-auto grid max-w-5xl items-center gap-8 md:grid-cols-2">
        <div>
          <p className="mc-hero-rise inline-block rounded-full bg-violet-100 px-4 py-1.5 text-xs font-black text-violet-700">
            {t("landing.badge")}
          </p>
          <h1
            id="landing-hero-title"
            className="mc-hero-rise mc-hero-rise-1 mt-4 text-4xl font-black leading-[1.25] text-stone-900 md:text-5xl md:leading-[1.3]"
          >
            {t("landing.hero.title")}
          </h1>
          <p className="mc-hero-rise mc-hero-rise-2 mt-4 max-w-xl text-base leading-8 text-stone-600 md:text-lg md:leading-9">
            {t("landing.hero.subtitle")}
          </p>
          <div className="mc-hero-rise mc-hero-rise-3 mt-6 flex flex-col gap-3 sm:flex-row">
            <Link
              to="/register"
              state={{ next: "/progress" }}
              className="flex min-h-[52px] flex-1 items-center justify-center rounded-2xl bg-violet-600 px-6 text-base font-black text-white shadow-md shadow-violet-200 active:bg-violet-700"
            >
              {t("landing.hero.primary")}
            </Link>
            <Link
              to="/login"
              className="flex min-h-[52px] flex-1 items-center justify-center rounded-2xl bg-amber-300 px-6 text-base font-black text-stone-900 active:bg-amber-400"
            >
              {t("landing.hero.secondary")}
            </Link>
          </div>
          <p className="mt-3 text-sm text-stone-500">{t("landing.hero.note")}</p>
        </div>
        <HeroVisual />
      </div>
    </section>
  );
}

// Decorative training composition: mini board island (LTR) framed by
// floating SVG pieces and product-metaphor chips. No real puzzle shown.
function HeroVisual() {
  return (
    <div className="mc-hero-rise mc-hero-rise-2 relative mx-auto w-full max-w-sm" aria-hidden="true">
      <div className="mc-dots absolute -inset-4 rounded-[2rem]" />
      <div className="relative rounded-[2rem] bg-white p-5 shadow-xl shadow-violet-200">
        <div dir="ltr" className="overflow-hidden rounded-2xl border-4 border-stone-900/80">
          <div className="grid grid-cols-4">
            <MiniSquare dark={false} piece="R" />
            <MiniSquare dark piece="N" />
            <MiniSquare dark={false} />
            <MiniSquare dark />
            <MiniSquare dark piece="P" />
            <MiniSquare dark={false} piece="P" />
            <MiniSquare dark />
            <MiniSquare dark={false} />
            <MiniSquare dark={false} />
            <MiniSquare dark piece="n" />
            <MiniSquare dark={false} piece="Q" />
            <MiniSquare dark />
            <MiniSquare dark piece="K" />
            <MiniSquare dark={false} />
            <MiniSquare dark piece="p" />
            <MiniSquare dark={false} />
          </div>
        </div>
        <div dir="rtl" className="mt-4 flex items-center justify-between gap-2">
          <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-black text-emerald-700">
            {t("feedback.correct")}
          </span>
          <span className="rounded-full bg-violet-100 px-3 py-1.5 text-xs font-black text-violet-700">
            {t("game.xp")} {faNum(124)}
          </span>
          <span className="rounded-full bg-amber-100 px-3 py-1.5 text-xs font-black text-amber-700">
            {t("game.streak")} {faNum(3)}
          </span>
        </div>
        <p className="mt-3 text-center text-xs font-bold text-stone-400">{t("landing.hero.boardCaption")}</p>
      </div>
      <div className="mc-float absolute -top-6 -start-4 w-16 drop-shadow-lg" style={{ "--mc-tilt": "-10deg" } as React.CSSProperties}>
        <ChessPiece symbol="N" />
      </div>
      <div className="mc-float mc-float-slow absolute -bottom-6 -end-3 w-14 drop-shadow-lg" style={{ "--mc-tilt": "8deg" } as React.CSSProperties}>
        <ChessPiece symbol="b" />
      </div>
    </div>
  );
}

function MiniSquare({ dark, piece }: { dark: boolean; piece?: "R" | "N" | "P" | "Q" | "K" | "n" | "p" }) {
  return (
    <div className={`aspect-square ${dark ? "bg-violet-300" : "bg-violet-50"}`}>
      {piece ? <ChessPiece symbol={piece} /> : null}
    </div>
  );
}

function ContrastSection() {
  return (
    <section aria-label={t("landing.why.title")} className="px-4 pb-4">
      <div className="mc-reveal mx-auto grid max-w-5xl gap-3 md:grid-cols-2">
        <div className="rounded-3xl border-2 border-dashed border-stone-200 bg-stone-50 p-6">
          <h2 className="text-lg font-black text-stone-400">{t("landing.contrast.playTitle")}</h2>
          <p className="mt-2 text-sm leading-7 text-stone-500">{t("landing.contrast.playDesc")}</p>
        </div>
        <div className="rounded-3xl bg-violet-600 p-6 shadow-lg shadow-violet-200">
          <h2 className="text-lg font-black text-white">{t("landing.contrast.trainTitle")}</h2>
          <p className="mt-2 text-sm leading-7 text-violet-100">{t("landing.contrast.trainDesc")}</p>
        </div>
      </div>
    </section>
  );
}

function WhySection() {
  const cards: Array<[string, string, string]> = [
    [t("landing.why.focusedTitle"), t("landing.why.focusedDesc"), "bg-violet-600 text-white"],
    [t("landing.why.shortTitle"), t("landing.why.shortDesc"), "bg-white text-stone-900"],
    [t("landing.why.feedbackTitle"), t("landing.why.feedbackDesc"), "bg-white text-stone-900"],
    [t("landing.why.visibleTitle"), t("landing.why.visibleDesc"), "bg-white text-stone-900"],
    [t("landing.why.fitTitle"), t("landing.why.fitDesc"), "bg-white text-stone-900"],
    [t("landing.why.habitTitle"), t("landing.why.habitDesc"), "bg-amber-300 text-stone-900"],
  ];
  return (
    <SectionShell
      id="why"
      eyebrow={t("landing.why.skillRange")}
      title={t("landing.why.title")}
      subtitle={t("landing.why.subtitle")}
    >
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map(([title, desc, tone]) => (
          <li key={title} className={`rounded-3xl p-5 shadow-md shadow-violet-100 ${tone}`}>
            <h3 className="text-base font-black">{title}</h3>
            <p className={`mt-1.5 text-sm leading-7 ${tone.startsWith("bg-white") ? "text-stone-500" : tone.includes("amber") ? "text-stone-700" : "text-violet-100"}`}>
              {desc}
            </p>
          </li>
        ))}
      </ul>
    </SectionShell>
  );
}

function FeaturesSection() {
  return (
    <SectionShell
      id="features"
      eyebrow={t("landing.nav.features")}
      title={t("landing.features.title")}
      subtitle={t("landing.features.subtitle")}
      tone="soft"
    >
      <div className="grid gap-3 md:grid-cols-3">
        <article className="rounded-3xl bg-violet-600 p-6 text-white shadow-lg shadow-violet-200 md:col-span-2">
          <h3 className="text-lg font-black">{t("landing.features.feedbackTitle")}</h3>
          <p className="mt-2 max-w-lg text-sm leading-8 text-violet-100">{t("landing.features.feedbackDesc")}</p>
          <div dir="ltr" className="mt-4 flex flex-wrap gap-2">
            <span className="rounded-full bg-white/15 px-4 py-1.5 text-xs font-black">{t("feedback.correct")}</span>
            <span className="rounded-full bg-white/15 px-4 py-1.5 text-xs font-black">{t("feedback.partial")}</span>
            <span className="rounded-full bg-white/15 px-4 py-1.5 text-xs font-black">{t("feedback.wrong")}</span>
          </div>
        </article>
        <article className="rounded-3xl bg-stone-900 p-6 text-white shadow-lg">
          <p className="text-3xl font-black text-amber-300">{faNum(124)}</p>
          <h3 className="mt-1 text-lg font-black">{t("landing.features.motivationTitle")}</h3>
          <p className="mt-2 text-sm leading-8 text-stone-300">{t("landing.features.motivationDesc")}</p>
        </article>
        <article className="rounded-3xl bg-white p-6 shadow-md shadow-violet-100 ring-1 ring-violet-100">
          <h3 className="text-base font-black text-stone-900">{t("landing.features.progressTitle")}</h3>
          <p className="mt-2 text-sm leading-8 text-stone-500">{t("landing.features.progressDesc")}</p>
        </article>
        <article className="rounded-3xl bg-white p-6 shadow-md shadow-violet-100 ring-1 ring-violet-100">
          <h3 className="text-base font-black text-stone-900">{t("landing.features.assistTitle")}</h3>
          <p className="mt-2 text-sm leading-8 text-stone-500">{t("landing.features.assistDesc")}</p>
        </article>
        <article className="rounded-3xl bg-white p-6 shadow-md shadow-violet-100 ring-1 ring-violet-100">
          <h3 className="text-base font-black text-stone-900">{t("landing.features.modesTitle")}</h3>
          <p className="mt-2 text-sm leading-8 text-stone-500">{t("landing.features.modesDesc")}</p>
        </article>
        <article className="rounded-3xl bg-amber-100 p-6 md:col-span-3">
          <h3 className="text-base font-black text-stone-900">{t("landing.features.familyTitle")}</h3>
          <p className="mt-2 max-w-3xl text-sm leading-8 text-stone-600">{t("landing.features.familyDesc")}</p>
        </article>
      </div>
    </SectionShell>
  );
}

function HowSection() {
  const steps: Array<[string, string]> = [
    [t("landing.how.s1t"), t("landing.how.s1d")],
    [t("landing.how.s2t"), t("landing.how.s2d")],
    [t("landing.how.s3t"), t("landing.how.s3d")],
    [t("landing.how.s4t"), t("landing.how.s4d")],
    [t("landing.how.s5t"), t("landing.how.s5d")],
  ];
  return (
    <SectionShell
      id="how"
      eyebrow={t("landing.nav.how")}
      title={t("landing.how.title")}
      subtitle={t("landing.how.subtitle")}
    >
      <ol className="grid gap-3 md:grid-cols-5">
        {steps.map(([title, desc], i) => (
          <li key={title} className="relative rounded-3xl bg-white p-5 shadow-md shadow-violet-100">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-violet-600 text-base font-black text-white">
              {faNum(i + 1)}
            </span>
            <h3 className="mt-3 text-sm font-black leading-6 text-stone-900">{title}</h3>
            <p className="mt-1 text-xs leading-6 text-stone-500">{desc}</p>
          </li>
        ))}
      </ol>
    </SectionShell>
  );
}

function PersonalSection() {
  return (
    <SectionShell
      id="personal"
      eyebrow={t("landing.personal.subtitle")}
      title={t("landing.personal.title")}
      tone="soft"
    >
      <div className="grid gap-3 md:grid-cols-2">
        <article className="rounded-3xl bg-violet-600 p-6 text-white shadow-lg shadow-violet-200">
          <p className="inline-block rounded-full bg-white/15 px-3 py-1 text-xs font-black">
            {t("landing.personal.nowTitle")}
          </p>
          <p className="mt-3 text-sm leading-8 text-violet-50">{t("landing.personal.nowDesc")}</p>
        </article>
        <article className="rounded-3xl bg-white p-6 shadow-md shadow-violet-100 ring-1 ring-dashed ring-violet-300">
          <p className="inline-block rounded-full bg-violet-100 px-3 py-1 text-xs font-black text-violet-700">
            {t("landing.personal.nextTitle")}
          </p>
          <p className="mt-3 text-sm leading-8 text-stone-600">{t("landing.personal.nextDesc")}</p>
        </article>
      </div>
      <div className="mt-4 flex flex-col items-center gap-3 rounded-3xl bg-stone-900 p-6 text-center md:flex-row md:justify-between md:text-start">
        <p className="text-sm font-bold leading-7 text-stone-200">{t("landing.personal.ctaNote")}</p>
        <Link
          to="/register"
          state={{ next: "/progress" }}
          className="flex min-h-[48px] shrink-0 items-center justify-center rounded-2xl bg-amber-300 px-6 text-base font-black text-stone-900 active:bg-amber-400"
        >
          {t("landing.hero.primary")}
        </Link>
      </div>
    </SectionShell>
  );
}

function ParentSection() {
  const items: Array<[string, string]> = [
    [t("landing.parent.q1"), t("landing.parent.a1")],
    [t("landing.parent.q2"), t("landing.parent.a2")],
    [t("landing.parent.q3"), t("landing.parent.a3")],
    [t("landing.parent.q4"), t("landing.parent.a4")],
    [t("landing.parent.q5"), t("landing.parent.a5")],
    [t("landing.parent.q6"), t("landing.parent.a6")],
  ];
  return (
    <SectionShell
      id="parents"
      eyebrow={t("landing.nav.why")}
      title={t("landing.parent.title")}
      subtitle={t("landing.parent.subtitle")}
    >
      <dl className="grid gap-3 md:grid-cols-2">
        {items.map(([q, a]) => (
          <div key={q} className="rounded-3xl bg-white p-5 shadow-md shadow-violet-100">
            <dt className="text-sm font-black leading-7 text-violet-700">{q}</dt>
            <dd className="mt-1 text-sm leading-7 text-stone-600">{a}</dd>
          </div>
        ))}
      </dl>
    </SectionShell>
  );
}

function ChildSection() {
  return (
    <SectionShell
      id="child"
      eyebrow={t("landing.child.subtitle")}
      title={t("landing.child.title")}
      tone="soft"
    >
      <div className="grid items-stretch gap-3 md:grid-cols-2">
        <div className="rounded-3xl bg-stone-900 p-6 text-white shadow-lg" dir="rtl">
          <p className="text-xs font-black text-stone-400">{t("exercises.piece-recognition.title")}</p>
          <div dir="ltr" className="mt-3 overflow-hidden rounded-2xl border-2 border-white/20">
            <div className="grid grid-cols-4">
              <MiniSquare dark={false} piece="N" />
              <MiniSquare dark />
              <MiniSquare dark={false} piece="P" />
              <MiniSquare dark />
              <MiniSquare dark />
              <MiniSquare dark={false} piece="N" />
              <MiniSquare dark />
              <MiniSquare dark={false} />
            </div>
          </div>
          <div className="mt-4 h-3 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
            <div className="h-full w-2/3 rounded-full bg-gradient-to-l from-violet-400 to-amber-300" />
          </div>
          <div className="mt-3 flex items-center justify-between text-xs font-bold text-stone-300">
            <span>
              {t("game.xp")} {faNum(40)}
            </span>
            <span>
              {t("game.streak")} {faNum(5)}
            </span>
          </div>
          <span className="mt-4 flex min-h-[48px] items-center justify-center rounded-2xl bg-violet-600 text-base font-black">
            {t("play.submit")}
          </span>
        </div>
        <ul className="grid content-stretch gap-3">
          {(
            [
              [t("landing.child.simpleTitle"), t("landing.child.simpleDesc")],
              [t("landing.child.quickTitle"), t("landing.child.quickDesc")],
              [t("landing.child.rewardTitle"), t("landing.child.rewardDesc")],
            ] as Array<[string, string]>
          ).map(([title, desc]) => (
            <li key={title} className="rounded-3xl bg-white p-5 shadow-md shadow-violet-100">
              <h3 className="text-base font-black text-stone-900">{title}</h3>
              <p className="mt-1 text-sm leading-7 text-stone-500">{desc}</p>
            </li>
          ))}
        </ul>
      </div>
    </SectionShell>
  );
}

function GuideSection() {
  const steps = [
    t("landing.guide.g1"),
    t("landing.guide.g2"),
    t("landing.guide.g3"),
    t("landing.guide.g4"),
    t("landing.guide.g5"),
  ];
  return (
    <SectionShell
      id="guide"
      eyebrow={t("landing.nav.guide")}
      title={t("landing.guide.title")}
      subtitle={t("landing.guide.subtitle")}
    >
      <div className="rounded-3xl bg-white p-6 shadow-md shadow-violet-100">
        <ol className="flex flex-col gap-1">
          {steps.map((step, i) => (
            <li key={step} className="flex min-h-[48px] items-center gap-3 border-b border-stone-100 py-2 last:border-0">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-violet-100 text-sm font-black text-violet-700">
                {faNum(i + 1)}
              </span>
              <span className="text-sm font-bold leading-7 text-stone-700">{step}</span>
            </li>
          ))}
        </ol>
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <Link
            to="/register"
            state={{ next: "/progress" }}
            className="flex min-h-[48px] items-center justify-center rounded-2xl bg-violet-600 px-5 text-base font-black text-white active:bg-violet-700"
          >
            {t("nav.register")}
          </Link>
          <Link
            to="/exercises"
            className="flex min-h-[48px] items-center justify-center rounded-2xl bg-violet-100 px-5 text-base font-black text-violet-700"
          >
            {t("landing.guide.catalogLink")}
          </Link>
        </div>
      </div>
    </SectionShell>
  );
}

function FreeSection() {
  return (
    <section aria-labelledby="free-title" className="px-4 pb-4">
      <div className="mc-reveal mx-auto max-w-5xl rounded-3xl bg-gradient-to-l from-violet-700 to-violet-500 p-8 text-center shadow-lg shadow-violet-200 md:p-12">
        <h2 id="free-title" className="text-2xl font-black text-white">
          {t("landing.free.title")}
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-sm leading-8 text-violet-100">{t("landing.free.desc")}</p>
        <Link
          to="/register"
          state={{ next: "/progress" }}
          className="mx-auto mt-6 flex min-h-[52px] max-w-xs items-center justify-center rounded-2xl bg-amber-300 px-6 text-base font-black text-stone-900 active:bg-amber-400"
        >
          {t("landing.hero.primary")}
        </Link>
        <Link
          to="/pricing"
          className="mx-auto mt-3 flex min-h-[44px] max-w-xs items-center justify-center rounded-2xl px-6 text-sm font-bold text-white underline"
        >
          {t("nav.pricing")}
        </Link>
      </div>
    </section>
  );
}

function FinalCta() {
  return (
    <section aria-labelledby="final-title" className="px-4 py-14 md:py-20">
      <div className="mc-reveal mx-auto max-w-3xl text-center">
        <div className="mx-auto flex w-fit items-end gap-2" aria-hidden="true">
          <span className="w-12 opacity-90">
            <ChessPiece symbol="k" />
          </span>
          <span className="w-16">
            <ChessPiece symbol="Q" />
          </span>
          <span className="w-12 opacity-90" style={{ transform: "scaleX(-1)" }}>
            <ChessPiece symbol="n" />
          </span>
        </div>
        <h2 id="final-title" className="mt-4 text-3xl font-black leading-snug text-stone-900 md:text-4xl">
          {t("landing.final.title")}
        </h2>
        <p className="mx-auto mt-3 max-w-xl text-base leading-8 text-stone-500">{t("landing.final.subtitle")}</p>
        <div className="mx-auto mt-6 flex max-w-lg flex-col gap-3 sm:flex-row">
          <Link
            to="/register"
            state={{ next: "/progress" }}
            className="flex min-h-[52px] flex-1 items-center justify-center rounded-2xl bg-violet-600 px-6 text-base font-black text-white shadow-md shadow-violet-200 active:bg-violet-700"
          >
            {t("landing.hero.primary")}
          </Link>
          <Link
            to="/login"
            className="flex min-h-[52px] flex-1 items-center justify-center rounded-2xl bg-white px-6 text-base font-black text-violet-700 shadow-md shadow-violet-100"
          >
            {t("landing.hero.secondary")}
          </Link>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="border-t border-violet-100 bg-white px-4 py-8">
      <div className="mx-auto flex max-w-5xl flex-col items-center gap-4 text-center">
        <p className="text-lg font-black text-violet-700">{t("app.name")}</p>
        <p className="max-w-md text-sm leading-7 text-stone-500">{t("landing.footer.about")}</p>
        <nav aria-label={t("app.name")} className="flex flex-wrap items-center justify-center gap-2">
          <Link
            to="/login"
            className="flex min-h-[44px] items-center rounded-2xl px-4 text-sm font-bold text-violet-700"
          >
            {t("nav.login")}
          </Link>
          <Link
            to="/register"
            className="flex min-h-[44px] items-center rounded-2xl px-4 text-sm font-bold text-violet-700"
          >
            {t("nav.register")}
          </Link>
          <Link
            to="/exercises"
            className="flex min-h-[44px] items-center rounded-2xl px-4 text-sm font-bold text-violet-700"
          >
            {t("landing.guide.catalogLink")}
          </Link>
        </nav>
        <p className="text-xs text-stone-400">© {t("landing.footer.rights")}</p>
      </div>
    </footer>
  );
}
