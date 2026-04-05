import { BarChart3, Briefcase, CheckCircle2, Compass, FileText, XCircle } from "lucide-react";
import { useNavigate } from "react-router";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useTaskStore, type CompletedTask, type RunningTask } from "@/stores/task-store";
import { cn } from "@/lib/utils";

const typeIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  scrape: Briefcase,
  analyze: BarChart3,
  generate: FileText,
  discover: Compass,
};

const typeLabels: Record<string, string> = {
  scrape: "Scraping job",
  analyze: "Analyzing job",
  generate: "Generating docs",
  discover: "Running discovery",
};

function elapsed(startedAt?: number): string {
  if (!startedAt) return "";
  const sec = Math.floor((Date.now() - startedAt) / 1000);
  if (sec < 60) return `${sec}s`;
  return `${Math.floor(sec / 60)}m ${sec % 60}s`;
}

function timeAgo(ts: number): string {
  const sec = Math.floor((Date.now() - ts) / 1000);
  if (sec < 60) return "just now";
  if (sec < 3600) return `${Math.floor(sec / 60)}m ago`;
  return `${Math.floor(sec / 3600)}h ago`;
}

function RunningTaskRow({ task }: { task: RunningTask }) {
  const Icon = typeIcons[task.type] || Briefcase;
  return (
    <div className="flex items-center gap-3 rounded-md border p-3">
      <Icon className="h-5 w-5 shrink-0 text-blue-500" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium">{typeLabels[task.type] || task.type}</span>
          <span className="text-xs text-muted-foreground">{elapsed(task.startedAt)}</span>
        </div>
        {task.message && <p className="truncate text-xs text-muted-foreground">{task.message}</p>}
        <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-muted">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${task.progress}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function CompletedTaskRow({ task }: { task: CompletedTask }) {
  const navigate = useNavigate();
  const Icon = task.status === "completed" ? CheckCircle2 : XCircle;
  const iconColor = task.status === "completed" ? "text-green-500" : "text-red-500";

  function handleClick() {
    if (task.status === "completed" && task.result?.job_id) {
      navigate(`/jobs/${task.result.job_id}`);
    }
  }

  return (
    <button
      onClick={handleClick}
      className={cn(
        "flex w-full items-center gap-3 rounded-md border p-3 text-left transition-colors",
        task.result?.job_id && "cursor-pointer hover:bg-accent",
      )}
    >
      <Icon className={cn("h-5 w-5 shrink-0", iconColor)} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between text-sm">
          <span>{typeLabels[task.type] || task.type}</span>
          <span className="text-xs text-muted-foreground">{timeAgo(task.completedAt)}</span>
        </div>
        {task.error && <p className="truncate text-xs text-red-500">{task.error}</p>}
      </div>
    </button>
  );
}

export function TaskDrawer() {
  const drawerOpen = useTaskStore((s) => s.drawerOpen);
  const toggleDrawer = useTaskStore((s) => s.toggleDrawer);
  const tasks = useTaskStore((s) => s.tasks);
  const recentTasks = useTaskStore((s) => s.recentTasks);

  return (
    <Sheet open={drawerOpen} onOpenChange={toggleDrawer}>
      <SheetContent side="right" className="w-[380px] sm:w-[420px]">
        <SheetHeader>
          <SheetTitle>Tasks</SheetTitle>
        </SheetHeader>
        <div className="mt-4 space-y-4 overflow-auto">
          {tasks.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Running</h3>
              <div className="space-y-2">
                {tasks.map((t) => <RunningTaskRow key={t.id} task={t} />)}
              </div>
            </div>
          )}
          {recentTasks.length > 0 && (
            <div>
              <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">Recent</h3>
              <div className="space-y-2">
                {recentTasks.map((t) => <CompletedTaskRow key={t.id} task={t} />)}
              </div>
            </div>
          )}
          {tasks.length === 0 && recentTasks.length === 0 && (
            <p className="py-8 text-center text-sm text-muted-foreground">No tasks yet</p>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
