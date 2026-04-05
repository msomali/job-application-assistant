import { Outlet, useLocation } from "react-router";
import { useTaskStream } from "@/hooks/use-task-stream";
import { IconRail } from "./icon-rail";
import { TopBar } from "./top-bar";
import { TaskDrawer } from "./task-drawer";

const pageTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/jobs": "Jobs",
  "/discover": "Discover",
  "/search": "Search",
  "/skills": "Skills",
  "/profile": "Profile",
  "/answers": "Answers",
  "/settings": "Settings",
  "/billing": "Billing",
  "/billing/plans": "Plans",
  "/billing/usage": "Usage",
  "/billing/history": "History",
};

export function AppShell() {
  const location = useLocation();
  useTaskStream();
  const title =
    pageTitles[location.pathname] ??
    Object.entries(pageTitles).find(([prefix]) => location.pathname.startsWith(prefix))?.[1] ??
    "JobAssist";
  return (
    <div className="flex h-screen overflow-hidden">
      <IconRail />
      <div className="flex flex-1 flex-col overflow-hidden">
        <TopBar title={title} />
        <main className="flex-1 overflow-auto p-5">
          <Outlet />
        </main>
      </div>
      <TaskDrawer />
    </div>
  );
}
