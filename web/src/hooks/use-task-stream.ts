import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { useTaskStore } from "@/stores/task-store";
import { queryKeys } from "@/lib/query-keys";

export function useTaskStream() {
  const token = useAuthStore((s) => s.token);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { addTask, updateTask, removeTask } = useTaskStore();
  const queryClient = useQueryClient();
  const retriesRef = useRef(0);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!isAuthenticated || !token) return;

    function connect() {
      const url = `${import.meta.env.VITE_API_URL || ""}/api/tasks/stream?token=${token}`;
      const es = new EventSource(url);
      esRef.current = es;

      es.addEventListener("task:started", (e) => {
        const data = JSON.parse(e.data);
        addTask({ id: data.task_id, type: data.type, progress: 0 });
        toast.info(`${data.type} task started`);
      });

      es.addEventListener("task:progress", (e) => {
        const data = JSON.parse(e.data);
        updateTask(data.task_id, { progress: data.progress, message: data.message });
      });

      es.addEventListener("task:completed", (e) => {
        const data = JSON.parse(e.data);
        removeTask(data.task_id);
        toast.success(`${data.type} completed`);
        if (data.type === "scrape" || data.type === "discover") {
          queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
        }
        if (data.type === "analyze") {
          queryClient.invalidateQueries({ queryKey: queryKeys.jobs.all });
          if (data.result?.job_id) {
            queryClient.invalidateQueries({ queryKey: queryKeys.analysis.byJob(data.result.job_id) });
          }
        }
        if (data.type === "generate") {
          if (data.result?.job_id) {
            queryClient.invalidateQueries({ queryKey: queryKeys.documents.byJob(data.result.job_id) });
          }
        }
      });

      es.addEventListener("task:failed", (e) => {
        const data = JSON.parse(e.data);
        removeTask(data.task_id);
        toast.error(`${data.type} failed: ${data.error || "Unknown error"}`);
      });

      es.addEventListener("ping", () => {
        retriesRef.current = 0;
      });

      es.onerror = () => {
        es.close();
        esRef.current = null;
        const delay = Math.min(1000 * 2 ** retriesRef.current, 30000);
        retriesRef.current++;
        setTimeout(connect, delay);
      };
    }

    connect();

    return () => {
      esRef.current?.close();
      esRef.current = null;
    };
  }, [isAuthenticated, token, addTask, updateTask, removeTask, queryClient]);
}
