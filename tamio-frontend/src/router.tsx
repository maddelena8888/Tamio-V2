import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import MainLayout from '@/layouts/MainLayout';

// V4 Primary Pages
import AlertHeroHome from '@/pages/AlertHeroHome';
import AlertImpact from '@/pages/AlertImpact';
import Dashboard from '@/pages/Dashboard';
import Tami from '@/pages/Tami';

// V3 Pages (retained)
import ClientsExpenses from '@/pages/ClientsExpenses';
import Scenarios from '@/pages/Scenarios';
import ScenarioBuilder from '@/pages/ScenarioBuilder';
import Settings from '@/pages/Settings';

// V5 Pages
import Forecast from '@/pages/Forecast';
import Health from '@/pages/Health';
import ForecastCanvas from '@/pages/ForecastCanvas';
import Projections from '@/pages/Projections';
import Rules from '@/pages/Rules';
import UnifiedForecast from '@/pages/UnifiedForecast';

// Auth & Onboarding
import Login from '@/pages/Login';
import Signup from '@/pages/Signup';
import ForgotPassword from '@/pages/ForgotPassword';
import ResetPassword from '@/pages/ResetPassword';
import Onboarding from '@/pages/Onboarding';
import OnboardingManual from '@/pages/OnboardingManual';
import OnboardingBusinessProfile from '@/pages/OnboardingBusinessProfile';

// Loading screen component
function LoadingScreen() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center space-y-4">
        <h1 className="text-2xl font-bold">TAMIO</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
    </div>
  );
}

// Protected route wrapper - for authenticated users who completed all onboarding
function ProtectedRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Redirect to business profile if not completed
  if (user && !user.business_profile_completed_at) {
    return <Navigate to="/onboarding/business-profile" replace />;
  }

  // Redirect to data source onboarding if not completed
  if (user && !user.has_completed_onboarding) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}

// Auth route wrapper (for login/signup pages)
function AuthRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (isAuthenticated && user) {
    // Redirect based on onboarding status
    if (!user.business_profile_completed_at) {
      return <Navigate to="/onboarding/business-profile" replace />;
    }
    if (!user.has_completed_onboarding) {
      return <Navigate to="/onboarding" replace />;
    }
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

// Business profile route wrapper - first onboarding step
function BusinessProfileRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // If business profile already completed, go to next step
  if (user && user.business_profile_completed_at) {
    if (user.has_completed_onboarding) {
      return <Navigate to="/" replace />;
    }
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}

// Onboarding route wrapper - for data source selection (after business profile)
function OnboardingRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return <LoadingScreen />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // If business profile not completed, go there first
  if (user && !user.business_profile_completed_at) {
    return <Navigate to="/onboarding/business-profile" replace />;
  }

  // If already completed onboarding, go to dashboard
  if (user && user.has_completed_onboarding) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

export const router = createBrowserRouter([
  // Auth routes (login, signup)
  {
    element: <AuthRoute />,
    children: [
      { path: '/login', element: <Login /> },
      { path: '/signup', element: <Signup /> },
      { path: '/forgot-password', element: <ForgotPassword /> },
      { path: '/reset-password', element: <ResetPassword /> },
    ],
  },
  // Business profile route (first onboarding step)
  {
    element: <BusinessProfileRoute />,
    children: [
      { path: '/onboarding/business-profile', element: <OnboardingBusinessProfile /> },
    ],
  },
  // Data source onboarding routes (after business profile)
  {
    element: <OnboardingRoute />,
    children: [
      { path: '/onboarding', element: <Onboarding /> },
      { path: '/onboarding/manual', element: <OnboardingManual /> },
    ],
  },
  // Protected app routes
  {
    element: <ProtectedRoute />,
    children: [
      {
        path: '/',
        element: <MainLayout />,
        children: [
          // Home page (Forecast Canvas)
          { index: true, element: <ForecastCanvas /> },
          // Alert Impact visualization route
          { path: 'alerts/:alertId/impact', element: <AlertImpact /> },
          { path: 'tami', element: <Tami /> },
          { path: 'dashboard', element: <Dashboard /> },
          { path: 'ledger', element: <ClientsExpenses /> },
          // Legacy route redirect
          { path: 'clients', element: <Navigate to="/ledger" replace /> },
          { path: 'scenarios', element: <Forecast /> },
          { path: 'scenarios/legacy', element: <Scenarios /> },
          { path: 'scenarios/builder', element: <ScenarioBuilder /> },
          { path: 'health', element: <Health /> },
          { path: 'home', element: <Navigate to="/" replace /> },
          { path: 'projections', element: <Projections /> },
          { path: 'forecast-scenarios', element: <UnifiedForecast /> },
          { path: 'rules', element: <Rules /> },
          // Placeholder routes for monitor card navigation
          { path: 'obligations', element: <Navigate to="/" replace /> },
          { path: 'receivables', element: <Navigate to="/" replace /> },
          { path: 'settings', element: <Settings /> },
        ],
      },
    ],
  },
  // Catch-all redirect
  {
    path: '*',
    element: <Navigate to="/" replace />,
  },
]);
