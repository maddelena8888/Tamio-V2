import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import {
  ChevronRight,
  ChevronLeft,
  ArrowRight,
  CheckCircle2,
  Circle,
  Plug,
  Eye,
  Bell,
  Sparkles,
  MousePointerClick,
  RefreshCw,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ============================================================================
// Types
// ============================================================================

interface DemoStep {
  id: number;
  title: string;
  subtitle: string;
  description: string;
  icon: React.ReactNode;
  visual: React.ReactNode;
}

// ============================================================================
// Step Visuals
// ============================================================================

function ConnectVisual() {
  const sources = [
    { name: 'Xero', status: 'connected', icon: '📊' },
    { name: 'Bank Feed', status: 'connected', icon: '🏦' },
    { name: 'Payroll', status: 'connected', icon: '💰' },
  ];

  return (
    <div className="space-y-3 max-w-sm mx-auto">
      {sources.map((source, i) => (
        <div
          key={i}
          className="flex items-center justify-between p-4 rounded-xl bg-white/60 border border-lime/30 shadow-sm"
        >
          <div className="flex items-center gap-3">
            <span className="text-2xl">{source.icon}</span>
            <span className="font-medium text-gunmetal">{source.name}</span>
          </div>
          <div className="flex items-center gap-2 text-sm text-green-600">
            <CheckCircle2 className="w-4 h-4" />
            Connected
          </div>
        </div>
      ))}
      <p className="text-xs text-center text-muted-foreground pt-2">
        Data syncs automatically every hour
      </p>
    </div>
  );
}

function SeeVisual() {
  const metrics = [
    { label: 'Cash Position', value: '$487K', trend: '+2.3%', healthy: true },
    { label: 'Runway', value: '52 weeks', trend: 'Stable', healthy: true },
    { label: 'Burn Rate', value: '$42K/wk', trend: '-5%', healthy: true },
  ];

  return (
    <div className="space-y-4 max-w-md mx-auto">
      <div className="grid grid-cols-3 gap-3">
        {metrics.map((metric, i) => (
          <div
            key={i}
            className="p-3 rounded-xl bg-white/60 border border-border text-center"
          >
            <p className="text-xs text-muted-foreground">{metric.label}</p>
            <p className="text-lg font-bold text-gunmetal">{metric.value}</p>
            <p className={cn(
              'text-xs',
              metric.healthy ? 'text-green-600' : 'text-tomato'
            )}>
              {metric.trend}
            </p>
          </div>
        ))}
      </div>
      {/* Mini forecast chart */}
      <div className="p-4 rounded-xl bg-white/60 border border-border">
        <p className="text-xs text-muted-foreground mb-3">13-Week Forecast</p>
        <div className="h-16 flex items-end gap-1">
          {[75, 72, 68, 65, 70, 74, 78, 82, 85, 88, 90, 92, 95].map((h, i) => (
            <div
              key={i}
              className="flex-1 bg-lime/60 rounded-t"
              style={{ height: `${h}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function AlertVisual() {
  return (
    <div className="max-w-md mx-auto">
      <div className="p-5 rounded-2xl bg-white/60 border-2 border-tomato/30 shadow-lg">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-2.5 h-2.5 rounded-full bg-tomato animate-pulse" />
          <span className="text-xs font-medium text-tomato uppercase tracking-wide">
            Attention Required
          </span>
        </div>
        <h3 className="text-lg font-bold text-gunmetal mb-2">
          Payroll at Risk
        </h3>
        <p className="text-sm text-muted-foreground mb-3">
          RetailCo's $52K invoice is 14 days overdue. Without it, Friday's payroll will be $12K short.
        </p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="px-2 py-1 rounded-full bg-gunmetal/10">Impact: High</span>
          <span className="px-2 py-1 rounded-full bg-gunmetal/10">Due: 3 days</span>
        </div>
      </div>
    </div>
  );
}

function ActionVisual() {
  const options = [
    { title: 'Chase Invoice', risk: 'Low', recommended: true },
    { title: 'Delay Vendor Payment', risk: 'Medium', recommended: false },
    { title: 'Both Actions', risk: 'Low', recommended: false },
  ];

  return (
    <div className="space-y-3 max-w-md mx-auto">
      <p className="text-sm text-center text-muted-foreground mb-2">
        TAMI prepared 3 options, ranked by risk:
      </p>
      {options.map((option, i) => (
        <div
          key={i}
          className={cn(
            'p-4 rounded-xl border transition-all',
            option.recommended
              ? 'bg-lime/10 border-lime/40 shadow-sm'
              : 'bg-white/40 border-border'
          )}
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {option.recommended ? (
                <CheckCircle2 className="w-5 h-5 text-green-600" />
              ) : (
                <Circle className="w-5 h-5 text-muted-foreground" />
              )}
              <div>
                <p className="font-medium text-gunmetal">{option.title}</p>
                <p className="text-xs text-muted-foreground">
                  Risk: {option.risk}
                </p>
              </div>
            </div>
            {option.recommended && (
              <span className="text-xs px-2 py-1 rounded-full bg-lime text-gunmetal font-medium">
                Recommended
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

function ExecuteVisual() {
  return (
    <div className="max-w-md mx-auto space-y-4">
      <div className="p-4 rounded-xl bg-white/60 border border-border">
        <p className="text-xs text-muted-foreground mb-2">Ready to send:</p>
        <div className="p-3 rounded-lg bg-gunmetal/5 text-sm">
          <p className="font-medium text-gunmetal mb-1">To: accounts@retailco.com</p>
          <p className="text-muted-foreground text-xs leading-relaxed">
            "Hi Sarah, I hope you're well. I wanted to follow up on invoice #1247 for $52,500, which was due on Jan 10th. Could you let me know when we can expect payment?..."
          </p>
        </div>
      </div>
      <div className="flex gap-3">
        <Button variant="outline" className="flex-1">Edit Message</Button>
        <Button className="flex-1 bg-gunmetal text-white">
          <CheckCircle2 className="w-4 h-4 mr-2" />
          Send Now
        </Button>
      </div>
      <p className="text-xs text-center text-muted-foreground">
        Or schedule for tomorrow at 9am
      </p>
    </div>
  );
}

function RepeatVisual() {
  return (
    <div className="max-w-sm mx-auto text-center space-y-4">
      <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-lime/20">
        <RefreshCw className="w-10 h-10 text-gunmetal" />
      </div>
      <div>
        <p className="font-medium text-gunmetal mb-1">Tamio watches 24/7</p>
        <p className="text-sm text-muted-foreground">
          The cycle continues automatically. New issues are detected, solutions are prepared, you just approve.
        </p>
      </div>
      <div className="flex justify-center gap-6 pt-2">
        <div className="text-center">
          <p className="text-2xl font-bold text-gunmetal">12</p>
          <p className="text-xs text-muted-foreground">Detection Rules</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gunmetal">5 min</p>
          <p className="text-xs text-muted-foreground">Critical Checks</p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-bold text-gunmetal">1 hr</p>
          <p className="text-xs text-muted-foreground">Routine Checks</p>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Demo Steps Data
// ============================================================================

const demoSteps: DemoStep[] = [
  {
    id: 1,
    title: 'Connect',
    subtitle: 'Link your data sources',
    description: 'Connect Xero, bank feeds, and payroll. Tamio pulls in all your financial data automatically.',
    icon: <Plug className="w-5 h-5" />,
    visual: <ConnectVisual />,
  },
  {
    id: 2,
    title: 'See',
    subtitle: 'Instant cash visibility',
    description: 'Your cash position, runway, and 13-week forecast — calculated automatically, updated continuously.',
    icon: <Eye className="w-5 h-5" />,
    visual: <SeeVisual />,
  },
  {
    id: 3,
    title: 'Get Alerted',
    subtitle: 'Problems found for you',
    description: 'Tamio monitors 24/7. When something needs attention, you\'re the first to know — before it becomes a crisis.',
    icon: <Bell className="w-5 h-5" />,
    visual: <AlertVisual />,
  },
  {
    id: 4,
    title: 'Review Options',
    subtitle: 'AI-prepared solutions',
    description: 'TAMI analyzes the problem and prepares ranked options. Each includes risk scores and ready-to-use content.',
    icon: <Sparkles className="w-5 h-5" />,
    visual: <ActionVisual />,
  },
  {
    id: 5,
    title: 'Execute',
    subtitle: 'One click to act',
    description: 'Approve the action. Messages are drafted, payments are queued. You\'re in control, but the work is done.',
    icon: <MousePointerClick className="w-5 h-5" />,
    visual: <ExecuteVisual />,
  },
  {
    id: 6,
    title: 'Repeat',
    subtitle: 'Continuous protection',
    description: 'The cycle continues. Tamio keeps watching, keeps preparing, keeps protecting your cash flow.',
    icon: <RefreshCw className="w-5 h-5" />,
    visual: <RepeatVisual />,
  },
];

// ============================================================================
// Progress Indicator
// ============================================================================

function StepIndicator({
  steps,
  currentStep,
  onStepClick
}: {
  steps: DemoStep[];
  currentStep: number;
  onStepClick: (step: number) => void;
}) {
  return (
    <div className="flex items-center justify-center gap-2 mb-8">
      {steps.map((step, index) => (
        <button
          key={step.id}
          onClick={() => onStepClick(index)}
          className="flex items-center group"
        >
          <div
            className={cn(
              'flex items-center justify-center w-10 h-10 rounded-full border-2 transition-all',
              index === currentStep
                ? 'bg-gunmetal border-gunmetal text-white scale-110'
                : index < currentStep
                ? 'bg-lime border-lime text-gunmetal'
                : 'bg-white/50 border-gray-300 text-gray-400'
            )}
          >
            {index < currentStep ? (
              <CheckCircle2 className="w-5 h-5" />
            ) : (
              step.icon
            )}
          </div>
          {index < steps.length - 1 && (
            <div
              className={cn(
                'w-8 h-0.5 mx-1',
                index < currentStep ? 'bg-lime' : 'bg-gray-300'
              )}
            />
          )}
        </button>
      ))}
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function DemoShowcase() {
  const [currentStep, setCurrentStep] = useState(0);
  const step = demoSteps[currentStep];

  const handleNext = () => {
    if (currentStep < demoSteps.length - 1) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1);
    }
  };

  return (
    <div className="min-h-[calc(100vh-8rem)] px-4 py-6">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-gunmetal mb-1">
            How Tamio Works
          </h1>
          <p className="text-muted-foreground">
            From chaos to control in 6 simple steps
          </p>
        </div>

        {/* Step Indicator */}
        <StepIndicator
          steps={demoSteps}
          currentStep={currentStep}
          onStepClick={setCurrentStep}
        />

        {/* Step Content */}
        <div className="bg-white/30 backdrop-blur-sm rounded-2xl border border-border shadow-lg overflow-hidden">
          {/* Step Header */}
          <div className="p-6 border-b border-border bg-white/50 text-center">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-gunmetal/10 text-sm font-medium text-gunmetal mb-3">
              Step {step.id} of {demoSteps.length}
            </div>
            <h2 className="text-2xl font-bold text-gunmetal mb-1">
              {step.title}
            </h2>
            <p className="text-muted-foreground">
              {step.subtitle}
            </p>
          </div>

          {/* Visual */}
          <div className="p-8">
            {step.visual}
          </div>

          {/* Description */}
          <div className="px-6 pb-6 text-center">
            <p className="text-muted-foreground max-w-md mx-auto">
              {step.description}
            </p>
          </div>

          {/* Navigation */}
          <div className="px-6 pb-6 flex items-center justify-between">
            <Button
              variant="outline"
              onClick={handlePrev}
              disabled={currentStep === 0}
            >
              <ChevronLeft className="w-4 h-4 mr-1" />
              Back
            </Button>

            {currentStep === demoSteps.length - 1 ? (
              <Button asChild className="bg-gunmetal text-white">
                <Link to="/login">
                  Try It Now
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Link>
              </Button>
            ) : (
              <Button onClick={handleNext} className="bg-gunmetal text-white">
                Next
                <ChevronRight className="w-4 h-4 ml-1" />
              </Button>
            )}
          </div>
        </div>

        {/* Value Props */}
        <div className="mt-8 grid grid-cols-3 gap-4 text-center">
          <div className="p-4 rounded-xl bg-white/30 border border-border">
            <p className="text-2xl font-bold text-gunmetal">45 min</p>
            <p className="text-xs text-muted-foreground">→ 2 min daily check</p>
          </div>
          <div className="p-4 rounded-xl bg-white/30 border border-border">
            <p className="text-2xl font-bold text-gunmetal">24/7</p>
            <p className="text-xs text-muted-foreground">Continuous monitoring</p>
          </div>
          <div className="p-4 rounded-xl bg-white/30 border border-border">
            <p className="text-2xl font-bold text-gunmetal">1 Click</p>
            <p className="text-xs text-muted-foreground">To execute actions</p>
          </div>
        </div>
      </div>
    </div>
  );
}
