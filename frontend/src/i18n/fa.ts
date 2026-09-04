// Persian strings first. English dict added later without changing call sites.
export const fa = {
  "app.name": "میکروچس",
  "app.tagline": "تمرین شطرنج برای بچه‌ها",
  "nav.home": "خانه",
  "nav.exercises": "تمرین‌ها",
  "home.title": "بازی کن، یاد بگیر!",
  "home.subtitle": "تمرین‌های کوتاه و سرگرم‌کننده شطرنج، قدم‌به‌قدم.",
  "home.cta": "شروع تمرین‌ها",
  "exercises.title": "تمرین‌ها",
  "exercises.empty": "به‌زودی تمرین‌های جدید اضافه می‌شود.",
  "exercise.comingSoon": "به‌زودی",
  "common.loading": "در حال بارگذاری…",
  "common.error": "مشکلی پیش آمد. دوباره تلاش کن.",
  "common.retry": "تلاش دوباره",
  "feedback.correct": "آفرین! درست بود.",
  "feedback.partial": "نزدیک بود! کمی دیگر دقت کن.",
  "feedback.wrong": "اشتباه شد؛ دوباره تلاش کن.",
  "feedback.timeout": "وقت تمام شد!",
  "feedback.skipped": "رد شد.",
  "feedback.abandoned": "نیمه‌تمام ماند.",
  "notFound.title": "صفحه پیدا نشد",
  "notFound.cta": "بازگشت به خانه",
} as const;

export type FaKey = keyof typeof fa;
