import { describe, it, expect, beforeEach } from "vitest";
import { useTaskStore } from "../task-store";

describe("task-store", () => {
  beforeEach(() => {
    useTaskStore.getState().clear();
  });

  it("adds a task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    expect(useTaskStore.getState().tasks).toHaveLength(1);
  });

  it("does not add duplicate task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 50 });
    expect(useTaskStore.getState().tasks).toHaveLength(1);
  });

  it("updates a task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    useTaskStore.getState().updateTask("t1", { progress: 75 });
    expect(useTaskStore.getState().tasks[0].progress).toBe(75);
  });

  it("removes a task", () => {
    useTaskStore.getState().addTask({ id: "t1", type: "scrape", progress: 0 });
    useTaskStore.getState().removeTask("t1");
    expect(useTaskStore.getState().tasks).toHaveLength(0);
  });
});
