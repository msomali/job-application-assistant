import { cn, scoreColor } from "@/lib/utils";

interface ScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

export function ScoreBadge({ score, size = "sm" }: ScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex min-w-[30px] items-center justify-center rounded px-2 py-0.5 text-xs font-semibold bg-muted text-muted-foreground">
        —
      </span>
    );
  }

  const sizeClasses = {
    sm: "min-w-[30px] px-2 py-0.5 text-xs",
    md: "min-w-[38px] px-3 py-1 text-sm",
    lg: "min-w-[46px] px-4 py-1.5 text-lg",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded font-bold",
        sizeClasses[size],
        scoreColor(score)
      )}
    >
      {score}
    </span>
  );
}
