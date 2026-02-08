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
import { DemoBanner } from '@/components/DemoBanner';
import { TAMIProvider } from '@/contexts/TAMIContext';
import { RulesProvider } from '@/contexts/RulesContext';
import { GlobalTAMIButton } from '@/components/chat/GlobalTAMIButton';
import { GlobalTAMIDrawer } from '@/components/chat/GlobalTAMIDrawer';
import { NotificationCentreProvider, NotificationCentre } from '@/components/notification-centre';
import { NotificationsDropdown } from '@/components/notifications/NotificationsDropdown';
import {
  BookOpen,
  Settings,
  Activity,
  LayoutDashboard,
  LineChart,
  Shield,
} from 'lucide-react';

// Navigation items - Home (TAMI + Alerts + KPIs) is primary
const navItems = [
  { title: 'Home', url: '/home', icon: LayoutDashboard },
  { title: 'Dashboard', url: '/health', icon: Activity },
  { title: 'Forecast', url: '/forecast-scenarios', icon: LineChart },
];

export default function MainLayout() {
  const location = useLocation();

  return (
    <TAMIProvider>
    <RulesProvider>
    <NotificationCentreProvider>
    <SidebarProvider defaultOpen={false}>
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
                    isActive={location.pathname === '/rules'}
                    className="h-12"
                  >
                    <Link to="/rules">
                      <Shield className="h-5 w-5" />
                      <span>Rules</span>
                    </Link>
                  </SidebarMenuButton>
                </TooltipTrigger>
                <TooltipContent side="right">Rules</TooltipContent>
              </Tooltip>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <Tooltip>
                <TooltipTrigger asChild>
                  <SidebarMenuButton
                    asChild
                    isActive={location.pathname === '/ledger' || location.pathname.startsWith('/ledger')}
                    className="h-12"
                  >
                    <Link to="/ledger">
                      <BookOpen className="h-5 w-5" />
                      <span>Ledger</span>
                    </Link>
                  </SidebarMenuButton>
                </TooltipTrigger>
                <TooltipContent side="right">Ledger</TooltipContent>
              </Tooltip>
            </SidebarMenuItem>
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

      <SidebarInset className="bg-gradient-ambient min-h-screen flex flex-col overflow-x-hidden">
        <DemoBanner />
        <header className="flex h-14 items-center gap-2 px-4 mt-2">
          <SidebarTrigger className="-ml-2" />
          <div className="flex-1" />
          <NotificationsDropdown />
        </header>
        <main className="flex-1 p-6 overflow-x-hidden overflow-y-auto">
          <Outlet />
        </main>
      </SidebarInset>

      {/* Global TAMI Chat */}
      <GlobalTAMIButton />
      <GlobalTAMIDrawer />

      {/* Notification Centre Modal */}
      <NotificationCentre />
    </SidebarProvider>
    </NotificationCentreProvider>
    </RulesProvider>
    </TAMIProvider>
  );
}
