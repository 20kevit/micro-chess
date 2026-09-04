import type { ReactNode } from "react";

// Small status badge (e.g. "coming soon").
export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-block rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-700">
      {children}
    </span>
  );
}
