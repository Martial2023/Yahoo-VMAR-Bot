"use client";

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";
import {
  ActivityIcon,
  Bot,
  LayoutDashboardIcon,
  ListChecksIcon,
  MessageSquareIcon,
  SettingsIcon,
  ShieldCheckIcon,
  TrendingUp,
} from "lucide-react";
import { NavMain } from "./nav-main";
import { NavUser } from "./nav-user";
import Link from "next/link";

const navMain = [
  { title: "Dashboard", url: "/dashboard", icon: <LayoutDashboardIcon /> },
  { title: "Activities", url: "/dashboard/activities", icon: <ActivityIcon /> },
  { title: "Cycles", url: "/dashboard/runs", icon: <ListChecksIcon /> },
  { title: "Comments", url: "/dashboard/comments", icon: <MessageSquareIcon /> },
  { title: "Whitelist", url: "/dashboard/whitelist", icon: <ShieldCheckIcon /> },
  { title: "Settings", url: "/dashboard/settings", icon: <SettingsIcon /> },
];

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild>
              <Link href="/dashboard">
                <TrendingUp />
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <h2 className="text-xl font-bold">
                    <span className="text-primary">VMAR Bot</span>
                  </h2>
                </div>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <NavMain items={navMain} />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  );
}
