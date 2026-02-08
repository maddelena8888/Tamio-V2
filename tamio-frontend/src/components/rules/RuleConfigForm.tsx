import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { type RuleType, type RuleConfig, generateRuleDescription } from '@/lib/api/rules';
import { CashBufferFields } from './fields/CashBufferFields';
import { TaxVATFields } from './fields/TaxVATFields';
import { PayrollFields } from './fields/PayrollFields';
import { ReceivablesFields } from './fields/ReceivablesFields';
import { UnusualActivityFields } from './fields/UnusualActivityFields';

interface RuleConfigFormProps {
  ruleType: RuleType;
  config: RuleConfig;
  name: string;
  onChange: (config: RuleConfig, name: string) => void;
}

export function RuleConfigForm({ ruleType, config, name, onChange }: RuleConfigFormProps) {
  const handleConfigChange = (newConfig: RuleConfig) => {
    onChange(newConfig, name);
  };

  const handleNameChange = (newName: string) => {
    onChange(config, newName);
  };

  // Generate preview text
  const previewText = generateRuleDescription({
    rule_type: ruleType,
    config,
  } as Parameters<typeof generateRuleDescription>[0]);

  return (
    <div className="space-y-6">
      {/* Rule Name */}
      <div className="space-y-2">
        <Label htmlFor="rule-name">Rule Name</Label>
        <Input
          id="rule-name"
          value={name}
          onChange={(e) => handleNameChange(e.target.value)}
          placeholder="Enter a name for this rule"
        />
      </div>

      {/* Type-specific fields */}
      <div className="space-y-4">
        {ruleType === 'cash_buffer' && (
          <CashBufferFields config={config} onChange={handleConfigChange} />
        )}
        {ruleType === 'tax_vat_reserve' && (
          <TaxVATFields config={config} onChange={handleConfigChange} />
        )}
        {ruleType === 'payroll' && (
          <PayrollFields config={config} onChange={handleConfigChange} />
        )}
        {ruleType === 'receivables' && (
          <ReceivablesFields config={config} onChange={handleConfigChange} />
        )}
        {ruleType === 'unusual_activity' && (
          <UnusualActivityFields config={config} onChange={handleConfigChange} />
        )}
      </div>

      {/* Preview */}
      <div className="p-4 rounded-xl bg-white/30 border border-white/40">
        <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
          Rule Preview
        </p>
        <p className="text-sm text-gunmetal">{previewText}</p>
      </div>
    </div>
  );
}
