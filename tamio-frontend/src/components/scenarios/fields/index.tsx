import type {
  ScenarioType,
  PaymentDelayParams,
  ClientLossParams,
  ClientGainParams,
  HiringParams,
  FiringParams,
  ContractorParams,
  ExpenseParams,
} from '../mockData';
import { PaymentDelayFields } from './PaymentDelayFields';
import { ClientLossFields } from './ClientLossFields';
import { ClientGainFields } from './ClientGainFields';
import { HiringFields } from './HiringFields';
import { FiringFields } from './FiringFields';
import { ContractorFields } from './ContractorFields';
import { ExpenseFields } from './ExpenseFields';

export type AnyScenarioParams =
  | PaymentDelayParams
  | ClientLossParams
  | ClientGainParams
  | HiringParams
  | FiringParams
  | ContractorParams
  | ExpenseParams;

interface ScenarioTypeFieldsProps {
  scenarioType: ScenarioType;
  params: Partial<AnyScenarioParams>;
  onChange: (params: Partial<AnyScenarioParams>) => void;
}

export function ScenarioTypeFields({ scenarioType, params, onChange }: ScenarioTypeFieldsProps) {
  switch (scenarioType) {
    case 'payment_delay_in':
      return (
        <PaymentDelayFields
          isIncoming={true}
          params={params as Partial<PaymentDelayParams>}
          onChange={onChange}
        />
      );
    case 'payment_delay_out':
      return (
        <PaymentDelayFields
          isIncoming={false}
          params={params as Partial<PaymentDelayParams>}
          onChange={onChange}
        />
      );
    case 'client_loss':
      return (
        <ClientLossFields
          params={params as Partial<ClientLossParams>}
          onChange={onChange}
        />
      );
    case 'client_gain':
      return (
        <ClientGainFields
          params={params as Partial<ClientGainParams>}
          onChange={onChange}
        />
      );
    case 'hiring':
      return (
        <HiringFields
          params={params as Partial<HiringParams>}
          onChange={onChange}
        />
      );
    case 'firing':
      return (
        <FiringFields
          params={params as Partial<FiringParams>}
          onChange={onChange}
        />
      );
    case 'contractor_gain':
      return (
        <ContractorFields
          isGain={true}
          params={params as Partial<ContractorParams>}
          onChange={onChange}
        />
      );
    case 'contractor_loss':
      return (
        <ContractorFields
          isGain={false}
          params={params as Partial<ContractorParams>}
          onChange={onChange}
        />
      );
    case 'increased_expense':
      return (
        <ExpenseFields
          isIncrease={true}
          params={params as Partial<ExpenseParams>}
          onChange={onChange}
        />
      );
    case 'decreased_expense':
      return (
        <ExpenseFields
          isIncrease={false}
          params={params as Partial<ExpenseParams>}
          onChange={onChange}
        />
      );
    default:
      return null;
  }
}

export { PaymentDelayFields } from './PaymentDelayFields';
export { ClientLossFields } from './ClientLossFields';
export { ClientGainFields } from './ClientGainFields';
export { HiringFields } from './HiringFields';
export { FiringFields } from './FiringFields';
export { ContractorFields } from './ContractorFields';
export { ExpenseFields } from './ExpenseFields';
