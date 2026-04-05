import { LogOut, Settings, User } from "lucide-react";
import { useNavigate } from "react-router";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { TaskIndicator } from "@/components/tasks/task-indicator";
import { TaskBadge } from "./task-badge";
import { ThemeToggle } from "./theme-toggle";
import { useAuthStore } from "@/stores/auth-store";
import { useLogout } from "@/hooks/use-auth";

interface TopBarProps { title: string; }

export function TopBar({ title }: TopBarProps) {
  const user = useAuthStore((s) => s.user);
  const { mutate: logout } = useLogout();
  const navigate = useNavigate();
  const initials = user?.email?.charAt(0).toUpperCase() ?? "?";
  return (
    <header className="flex h-12 items-center justify-between border-b px-5">
      <h1 className="text-[15px] font-semibold">{title}</h1>
      <div className="flex items-center gap-3">
        <TaskIndicator />
        <div className="flex md:hidden">
          <TaskBadge />
        </div>
        <span className="rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">Free plan</span>
        <ThemeToggle />
        <DropdownMenu>
          <DropdownMenuTrigger
            render={
              <Button variant="ghost" className="h-8 w-8 rounded-full p-0">
                <Avatar className="h-7 w-7">
                  <AvatarFallback className="text-xs">{initials}</AvatarFallback>
                </Avatar>
              </Button>
            }
          />
          <DropdownMenuContent align="end" className="w-48">
            <DropdownMenuItem onClick={() => navigate("/profile")}>
              <User className="mr-2 h-4 w-4" /> Profile
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings className="mr-2 h-4 w-4" /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => { logout(); navigate("/login"); }}>
              <LogOut className="mr-2 h-4 w-4" /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
