import { create } from "zustand";

export interface RunningTask { id: string; type: string; progress: number; message?: string; }

interface TaskState {
  tasks: RunningTask[];
  addTask: (task: RunningTask) => void;
  updateTask: (id: string, updates: Partial<RunningTask>) => void;
  removeTask: (id: string) => void;
  clear: () => void;
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  addTask: (task) => set((s) => ({ tasks: s.tasks.some((t) => t.id === task.id) ? s.tasks : [...s.tasks, task] })),
  updateTask: (id, updates) => set((s) => ({ tasks: s.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)) })),
  removeTask: (id) => set((s) => ({ tasks: s.tasks.filter((t) => t.id !== id) })),
  clear: () => set({ tasks: [] }),
}));
