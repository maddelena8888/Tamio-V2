import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Share2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { Risk } from '@/lib/api/alertsActions';

interface ImpactHeaderProps {
  alert: Risk;
  onShare: () => void;
}

export function ImpactHeader({ alert, onShare }: ImpactHeaderProps) {
  const navigate = useNavigate();

  return (
    <div className="mb-8">
      {/* Top row: Back, Title, Share */}
      <div className="flex items-center justify-between">
        {/* Back button */}
        <Button
          variant="ghost"
          onClick={() => navigate(-1)}
          className="text-gunmetal hover:bg-white/50"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>

        {/* Alert title - centered */}
        <h1 className="text-2xl font-bold text-gunmetal text-center flex-1 px-4">
          {alert.title}
        </h1>

        {/* Share button */}
        <Button
          variant="outline"
          onClick={onShare}
          className="border-2 border-tomato/20 text-gunmetal hover:bg-tomato/5"
        >
          <Share2 className="h-4 w-4 mr-2" />
          Share
        </Button>
      </div>

      {/* Impact statement - quantified risk summary */}
      {alert.impact_statement && (
        <p className="text-center text-lg text-gunmetal/80 mt-4">
          {alert.impact_statement}
        </p>
      )}
    </div>
  );
}
