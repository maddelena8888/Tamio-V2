import { Link } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { AlertCircle } from 'lucide-react';

export function DemoBanner() {
  const { isDemo } = useAuth();

  if (!isDemo) return null;

  return (
    <div className="bg-lime text-gunmetal px-4 py-2.5 text-center text-sm font-medium sticky top-0 z-50">
      <div className="flex items-center justify-center gap-2 flex-wrap">
        <AlertCircle className="h-4 w-4" />
        <span>You're viewing a demo account with sample data</span>
        <span className="hidden sm:inline">-</span>
        <Link
          to="/signup"
          className="underline font-semibold hover:opacity-80 transition-opacity"
        >
          Sign up to save your own data
        </Link>
      </div>
    </div>
  );
}
