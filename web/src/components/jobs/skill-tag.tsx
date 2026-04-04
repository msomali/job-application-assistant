import { cn } from "@/lib/utils";

interface SkillTagProps {
  name: string;
  variant: "match" | "gap";
}

export function SkillTag({ name, variant }: SkillTagProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium",
        variant === "match"
          ? "bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300"
          : "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300"
      )}
    >
      {variant === "gap" ? `Gap: ${name}` : name}
    </span>
  );
}
