import { createBrowserRouter, Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import MainLayout from '@/layouts/MainLayout';
import Dashboard from '@/pages/Dashboard';
import ClientsExpenses from '@/pages/ClientsExpenses';
import Scenarios from '@/pages/Scenarios';
import Insights from '@/pages/Insights';
import Tami from '@/pages/Tami';
import Settings from '@/pages/Settings';
import Login from '@/pages/Login';
import Signup from '@/pages/Signup';
import ForgotPassword from '@/pages/ForgotPassword';
import ResetPassword from '@/pages/ResetPassword';
import Onboarding from '@/pages/Onboarding';
import OnboardingManual from '@/pages/OnboardingManual';

// Protected route wrapper
function ProtectedRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold">TAMIO</h1>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Redirect to onboarding if not completed
  if (user && !user.has_completed_onboarding) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}

// Auth route wrapper (for login/signup pages)
function AuthRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold">TAMIO</h1>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // If authenticated but hasn't completed onboarding, go to onboarding
  if (isAuthenticated && user && !user.has_completed_onboarding) {
    return <Navigate to="/onboarding" replace />;
  }

  // If authenticated and onboarding completed, go to dashboard
  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
}

// Onboarding route wrapper
function OnboardingRoute() {
  const { isAuthenticated, isLoading, user } = useAuth();

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center space-y-4">
          <h1 className="text-2xl font-bold">TAMIO</h1>
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
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
  // Onboarding routes
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
          { index: true, element: <Dashboard /> },
          { path: 'clients', element: <ClientsExpenses /> },
          { path: 'scenarios', element: <Scenarios /> },
          { path: 'insights', element: <Insights /> },
          { path: 'tami', element: <Tami /> },
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
