import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react';
import type { User } from '@/lib/api/types';
import {
  login as apiLogin,
  signup as apiSignup,
  logout as apiLogout,
  getCurrentUser,
  getStoredUser,
  isAuthenticated,
  completeOnboarding as apiCompleteOnboarding,
  demoLogin as apiDemoLogin,
} from '@/lib/api/auth';
import { getAccessToken } from '@/lib/api/client';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  isDemo: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  demoLogin: () => Promise<void>;
  logout: () => void;
  completeOnboarding: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const initAuth = async () => {
      const token = getAccessToken();
      if (token) {
        // Try to get stored user first for quick render
        const storedUser = getStoredUser();
        if (storedUser) {
          setUser(storedUser);
        }
        // Then validate with server
        try {
          const currentUser = await getCurrentUser();
          setUser(currentUser);
          localStorage.setItem('tamio_user', JSON.stringify(currentUser));
        } catch {
          // Token invalid, clear auth
          apiLogout();
          setUser(null);
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiLogin({ email, password });
    setUser(response.user);
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const response = await apiSignup({ email, password });
    setUser(response.user);
  }, []);

  const demoLogin = useCallback(async () => {
    const response = await apiDemoLogin();
    setUser(response.user);
  }, []);

  const logout = useCallback(() => {
    apiLogout();
    setUser(null);
  }, []);

  const completeOnboarding = useCallback(async () => {
    const updatedUser = await apiCompleteOnboarding();
    setUser(updatedUser);
    localStorage.setItem('tamio_user', JSON.stringify(updatedUser));
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const currentUser = await getCurrentUser();
      setUser(currentUser);
      localStorage.setItem('tamio_user', JSON.stringify(currentUser));
    } catch {
      // Ignore errors
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: isAuthenticated() && !!user,
        isDemo: user?.is_demo ?? false,
        login,
        signup,
        demoLogin,
        logout,
        completeOnboarding,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
