import { Activity } from "lucide-react";
import { useTaskStore } from "@/stores/task-store";
import { cn } from "@/lib/utils";

export function TaskBadge() {
  const taskCount = useTaskStore((s) => s.tasks.length);
  const toggleDrawer = useTaskStore((s) => s.toggleDrawer);

  return (
    <button
      onClick={toggleDrawer}
      className="relative flex h-9 w-full items-center gap-3 rounded-md px-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
      aria-label={`${taskCount} active tasks`}
    >
      <Activity className="h-5 w-5 shrink-0" />
      <span className="truncate text-sm opacity-0 transition-opacity duration-200 group-hover/rail:opacity-100">
        Tasks
      </span>
      {taskCount > 0 && (
        <span
          className={cn(
            "absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-medium text-white",
            "animate-pulse",
          )}
        >
          {taskCount}
        </span>
      )}
    </button>
  );
}
