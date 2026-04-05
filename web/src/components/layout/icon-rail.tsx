import {
  Briefcase,
  Compass,
  Globe,
  LayoutDashboard,
  MessageSquare,
  Settings,
  TrendingUp,
  User,
} from "lucide-react";
import { NavLink } from "react-router";
import { cn } from "@/lib/utils";
import { TaskBadge } from "./task-badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/discover", icon: Compass, label: "Discover" },
  { to: "/search", icon: Globe, label: "Search" },
  { to: "/skills", icon: TrendingUp, label: "Skills" },
  { to: "/profile", icon: User, label: "Profile" },
  { to: "/answers", icon: MessageSquare, label: "Answers" },
];
const bottomItems = [{ to: "/settings", icon: Settings, label: "Settings" }];

export function IconRail() {
  return (
    <TooltipProvider delay={0}>
      <nav className="group/rail flex w-[52px] flex-col items-center gap-1 border-r bg-muted/40 px-2 py-3 transition-all duration-200 hover:w-[200px]">
        <NavLink
          to="/dashboard"
          className="mb-3 flex h-8 w-8 items-center justify-center rounded-md text-lg font-bold text-primary"
        >
          J
        </NavLink>
        {navItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
        <div className="mt-auto" />
        <TaskBadge />
        {bottomItems.map((item) => (
          <NavItem key={item.to} {...item} />
        ))}
      </nav>
    </TooltipProvider>
  );
}

function NavItem({
  to,
  icon: Icon,
  label,
}: {
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <NavLink
            to={to}
            className={({ isActive }) =>
              cn(
                "flex h-9 w-full items-center gap-3 rounded-md px-2 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground",
                isActive && "bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400",
              )
            }
          >
            <Icon className="h-5 w-5 shrink-0" />
            <span className="truncate text-sm opacity-0 transition-opacity duration-200 group-hover/rail:opacity-100">
              {label}
            </span>
          </NavLink>
        }
      />
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}
