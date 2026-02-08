import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { type AlertPreferences, type AlertFrequency } from '@/lib/api/rules';

interface RuleAlertPreferencesProps {
  preferences: AlertPreferences;
  onChange: (preferences: AlertPreferences) => void;
}

export function RuleAlertPreferences({ preferences, onChange }: RuleAlertPreferencesProps) {
  const handleChannelChange = (channel: 'show_in_feed' | 'send_email' | 'send_slack', checked: boolean) => {
    onChange({
      ...preferences,
      [channel]: checked,
    });
  };

  const handleFrequencyChange = (frequency: AlertFrequency) => {
    onChange({
      ...preferences,
      frequency,
    });
  };

  return (
    <div className="space-y-8">
      {/* Notification Channels */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-gunmetal">How should we alert you?</h3>
          <p className="text-sm text-muted-foreground mt-1">
            Choose at least one notification channel
          </p>
        </div>

        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Checkbox
              id="show_in_feed"
              checked={preferences.show_in_feed}
              onCheckedChange={(checked) => handleChannelChange('show_in_feed', checked as boolean)}
            />
            <Label htmlFor="show_in_feed" className="cursor-pointer">
              Show in Tamio alerts feed
            </Label>
          </div>

          <div className="flex items-center gap-3">
            <Checkbox
              id="send_email"
              checked={preferences.send_email}
              onCheckedChange={(checked) => handleChannelChange('send_email', checked as boolean)}
            />
            <Label htmlFor="send_email" className="cursor-pointer">
              Send email notification
            </Label>
          </div>

          <div className="flex items-center gap-3">
            <Checkbox
              id="send_slack"
              checked={preferences.send_slack}
              onCheckedChange={(checked) => handleChannelChange('send_slack', checked as boolean)}
              disabled
            />
            <Label htmlFor="send_slack" className="cursor-pointer text-muted-foreground">
              Send Slack notification
              <span className="ml-2 text-xs bg-white/50 px-2 py-0.5 rounded-full">
                Connect Slack
              </span>
            </Label>
          </div>
        </div>
      </div>

      {/* Alert Frequency */}
      <div className="space-y-4">
        <div>
          <h3 className="text-sm font-medium text-gunmetal">Alert frequency</h3>
          <p className="text-sm text-muted-foreground mt-1">
            How often should we send you alerts?
          </p>
        </div>

        <RadioGroup
          value={preferences.frequency}
          onValueChange={(value) => handleFrequencyChange(value as AlertFrequency)}
          className="space-y-3"
        >
          <div className="flex items-start gap-3">
            <RadioGroupItem value="every_time" id="every_time" className="mt-0.5" />
            <Label htmlFor="every_time" className="cursor-pointer">
              <span className="font-medium">Every time condition is met</span>
              <p className="text-sm text-muted-foreground">
                Get notified immediately when the rule triggers
              </p>
            </Label>
          </div>

          <div className="flex items-start gap-3">
            <RadioGroupItem value="daily_digest" id="daily_digest" className="mt-0.5" />
            <Label htmlFor="daily_digest" className="cursor-pointer">
              <span className="font-medium">Once per day (digest)</span>
              <p className="text-sm text-muted-foreground">
                Receive a daily summary of all triggered alerts
              </p>
            </Label>
          </div>

          <div className="flex items-start gap-3">
            <RadioGroupItem value="weekly_summary" id="weekly_summary" className="mt-0.5" />
            <Label htmlFor="weekly_summary" className="cursor-pointer">
              <span className="font-medium">Once per week (summary)</span>
              <p className="text-sm text-muted-foreground">
                Receive a weekly summary of rule activity
              </p>
            </Label>
          </div>
        </RadioGroup>
      </div>
    </div>
  );
}
