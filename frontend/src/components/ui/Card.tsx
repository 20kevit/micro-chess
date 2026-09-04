import type { ReactNode } from "react";

// Card container for pages and exercises.
export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-3xl bg-white p-4 shadow-md shadow-violet-100 ${className}`}>
      {children}
    </div>
  );
}
