import type { ButtonHTMLAttributes } from "react";

// Small reusable design system: friendly, rounded, touch-sized (min 44px).
type Variant = "primary" | "secondary" | "ghost";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
}

const styles: Record<Variant, string> = {
  primary: "bg-violet-600 text-white active:bg-violet-700",
  secondary: "bg-amber-300 text-stone-900 active:bg-amber-400",
  ghost: "bg-transparent text-violet-700",
};

export function Button({ variant = "primary", className = "", ...rest }: Props) {
  return (
    <button
      className={`min-h-[44px] rounded-2xl px-5 py-3 text-base font-bold shadow-sm transition ${styles[variant]} ${className}`}
      {...rest}
    />
  );
}
