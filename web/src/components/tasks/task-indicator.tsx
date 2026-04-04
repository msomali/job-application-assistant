import { Loader2 } from "lucide-react";
import { useTaskStore } from "@/stores/task-store";

export function TaskIndicator() {
  const count = useTaskStore((s) => s.tasks.length);
  if (count === 0) return null;
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
      <Loader2 className="h-3 w-3 animate-spin" />
      {count} task{count !== 1 ? "s" : ""} running
    </span>
  );
}
