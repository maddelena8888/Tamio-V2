import { Link, Outlet, useLocation } from 'react-router-dom';
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarInset,
  SidebarTrigger,
  SidebarRail,
} from '@/components/ui/sidebar';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  LayoutDashboard,
  Users,
  LineChart,
  Lightbulb,
  Bot,
  Settings,
} from 'lucide-react';

const navItems = [
  { title: 'Scenarios', url: '/scenarios', icon: LineChart },
  { title: 'Insights', url: '/insights', icon: Lightbulb },
  { title: 'Clients & Expenses', url: '/clients', icon: Users },
  { title: 'TAMI', url: '/tami', icon: Bot },
];

export default function MainLayout() {
  const location = useLocation();

  return (
    <SidebarProvider>
      <Sidebar
        className="border-r-0"
        collapsible="icon"
      >
        <SidebarHeader className="p-4">
          <Link to="/" className="flex items-center gap-2">
            <img
              src="/logo-sidebar-light.svg"
              alt="Tamio"
              className="w-10 h-10 hidden group-data-[collapsible=icon]:block"
            />
            <img
              src="/logo-light.svg"
              alt="Tamio"
              className="h-6 group-data-[collapsible=icon]:hidden"
            />
          </Link>
        </SidebarHeader>

        <SidebarContent className="px-2 pt-1 overflow-visible">
          <SidebarMenu>
            {/* Dashboard link */}
            <SidebarMenuItem>
              <Tooltip>
                <TooltipTrigger asChild>
                  <SidebarMenuButton
                    asChild
                    isActive={location.pathname === '/'}
                    className="h-12"
                  >
                    <Link to="/">
                      <LayoutDashboard className="h-5 w-5" />
                      <span>Dashboard</span>
                    </Link>
                  </SidebarMenuButton>
                </TooltipTrigger>
                <TooltipContent side="right">Dashboard</TooltipContent>
              </Tooltip>
            </SidebarMenuItem>

            {/* Main navigation */}
            {navItems.map((item) => (
              <SidebarMenuItem key={item.title}>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <SidebarMenuButton
                      asChild
                      isActive={location.pathname === item.url}
                      className="h-12"
                    >
                      <Link to={item.url}>
                        <item.icon className="h-5 w-5" />
                        <span>{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </TooltipTrigger>
                  <TooltipContent side="right">{item.title}</TooltipContent>
                </Tooltip>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>

        <SidebarFooter className="p-2">
          <SidebarMenu>
            <SidebarMenuItem>
              <Tooltip>
                <TooltipTrigger asChild>
                  <SidebarMenuButton
                    asChild
                    isActive={location.pathname === '/settings'}
                    className="h-12"
                  >
                    <Link to="/settings">
                      <Settings className="h-5 w-5" />
                      <span>Settings</span>
                    </Link>
                  </SidebarMenuButton>
                </TooltipTrigger>
                <TooltipContent side="right">Settings</TooltipContent>
              </Tooltip>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
        <SidebarRail />
      </Sidebar>

      <SidebarInset className="bg-gradient-ambient min-h-screen">
        <header className="flex h-14 items-center gap-2 px-4">
          <SidebarTrigger className="-ml-2" />
        </header>
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </SidebarInset>
    </SidebarProvider>
  );
}
