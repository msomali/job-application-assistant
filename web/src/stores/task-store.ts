import { create } from "zustand";

export interface RunningTask {
  id: string;
  type: string;
  progress: number;
  message?: string;
  startedAt?: number;
}

export interface CompletedTask {
  id: string;
  type: string;
  status: "completed" | "failed";
  result?: Record<string, unknown>;
  error?: string;
  completedAt: number;
}

interface TaskState {
  tasks: RunningTask[];
  recentTasks: CompletedTask[];
  drawerOpen: boolean;
  addTask: (task: RunningTask) => void;
  updateTask: (id: string, updates: Partial<RunningTask>) => void;
  completeTask: (id: string, result?: Record<string, unknown>) => void;
  failTask: (id: string, error?: string) => void;
  removeTask: (id: string) => void;
  toggleDrawer: () => void;
  clear: () => void;
}

const MAX_RECENT = 10;
const RECENT_TTL_MS = 60 * 60 * 1000; // 1 hour

function pruneRecent(tasks: CompletedTask[]): CompletedTask[] {
  const cutoff = Date.now() - RECENT_TTL_MS;
  return tasks.filter((t) => t.completedAt > cutoff).slice(0, MAX_RECENT);
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  recentTasks: [],
  drawerOpen: false,
  addTask: (task) =>
    set((s) => ({
      tasks: s.tasks.some((t) => t.id === task.id)
        ? s.tasks
        : [...s.tasks, { ...task, startedAt: task.startedAt ?? Date.now() }],
    })),
  updateTask: (id, updates) =>
    set((s) => ({
      tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),
  completeTask: (id, result) =>
    set((s) => {
      const task = s.tasks.find((t) => t.id === id);
      return {
        tasks: s.tasks.filter((t) => t.id !== id),
        recentTasks: pruneRecent([
          { id, type: task?.type ?? "unknown", status: "completed", result, completedAt: Date.now() },
          ...s.recentTasks,
        ]),
      };
    }),
  failTask: (id, error) =>
    set((s) => {
      const task = s.tasks.find((t) => t.id === id);
      return {
        tasks: s.tasks.filter((t) => t.id !== id),
        recentTasks: pruneRecent([
          { id, type: task?.type ?? "unknown", status: "failed", error, completedAt: Date.now() },
          ...s.recentTasks,
        ]),
      };
    }),
  removeTask: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),
  toggleDrawer: () => set((s) => ({ drawerOpen: !s.drawerOpen })),
  clear: () => set({ tasks: [], recentTasks: [] }),
}));
