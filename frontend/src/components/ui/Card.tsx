import type { ReactNode } from "react";

// Card container for pages and exercises.
export function Card({ children, className = "", "data-testid": testId }: { children: ReactNode; className?: string; "data-testid"?: string }) {
  return (
    <div data-testid={testId} className={`rounded-3xl bg-white p-4 shadow-md shadow-violet-100 ${className}`}>
      {children}
    </div>
  );
}
