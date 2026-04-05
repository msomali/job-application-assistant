import { Briefcase, Compass, Globe, LayoutDashboard, Menu } from "lucide-react";
import { NavLink } from "react-router";
import { useState } from "react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { MessageSquare, Settings, TrendingUp, User, CreditCard } from "lucide-react";

const tabs = [
  { to: "/dashboard", icon: LayoutDashboard, label: "Home" },
  { to: "/jobs", icon: Briefcase, label: "Jobs" },
  { to: "/discover", icon: Compass, label: "Discover" },
  { to: "/search", icon: Globe, label: "Search" },
];

const moreItems = [
  { to: "/skills", icon: TrendingUp, label: "Skills" },
  { to: "/profile", icon: User, label: "Profile" },
  { to: "/answers", icon: MessageSquare, label: "Answers" },
  { to: "/settings", icon: Settings, label: "Settings" },
  { to: "/billing", icon: CreditCard, label: "Billing" },
];

export function MobileNav() {
  const [moreOpen, setMoreOpen] = useState(false);

  return (
    <>
      <nav className="fixed inset-x-0 bottom-0 z-50 flex h-14 items-center justify-around border-t bg-background md:hidden">
        {tabs.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 px-3 py-1 text-muted-foreground",
                isActive && "text-blue-600 dark:text-blue-400",
              )
            }
          >
            <item.icon className="h-5 w-5" />
            <span className="text-[10px]">{item.label}</span>
          </NavLink>
        ))}
        <button
          onClick={() => setMoreOpen(true)}
          className="flex flex-col items-center gap-0.5 px-3 py-1 text-muted-foreground"
        >
          <Menu className="h-5 w-5" />
          <span className="text-[10px]">More</span>
        </button>
      </nav>
      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent side="bottom" className="rounded-t-xl">
          <SheetHeader>
            <SheetTitle>More</SheetTitle>
          </SheetHeader>
          <div className="grid grid-cols-3 gap-4 py-4">
            {moreItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => setMoreOpen(false)}
                className="flex flex-col items-center gap-1.5 rounded-lg p-3 text-muted-foreground hover:bg-accent"
              >
                <item.icon className="h-6 w-6" />
                <span className="text-xs">{item.label}</span>
              </NavLink>
            ))}
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
}
