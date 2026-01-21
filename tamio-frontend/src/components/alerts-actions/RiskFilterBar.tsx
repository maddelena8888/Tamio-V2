/**
 * RiskFilterBar Component - V4 Risk/Controls Architecture
 *
 * Dropdown-based filters for risks, replacing the old pill-based UI.
 * Includes:
 * - Priority dropdown (Urgent/High/Normal/All)
 * - Timing dropdown (Due today/This week/Next 2 weeks/All)
 */

import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Filter, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { RiskFilters } from '@/lib/api/alertsActions';

interface RiskFilterBarProps {
  filters: RiskFilters;
  onFiltersChange: (filters: RiskFilters) => void;
  totalCount: number;
  filteredCount: number;
  isLoading: boolean;
  onRefresh: () => void;
}

export function RiskFilterBar({
  filters,
  onFiltersChange,
  totalCount,
  filteredCount,
  isLoading,
  onRefresh,
}: RiskFilterBarProps) {
  const handleSeverityChange = (value: string) => {
    onFiltersChange({
      ...filters,
      severity: value as RiskFilters['severity'],
    });
  };

  const handleTimingChange = (value: string) => {
    onFiltersChange({
      ...filters,
      timing: value as RiskFilters['timing'],
    });
  };

  const hasActiveFilters =
    (filters.severity && filters.severity !== 'all') ||
    (filters.timing && filters.timing !== 'all');

  const clearFilters = () => {
    onFiltersChange({
      severity: 'all',
      timing: 'all',
      status: 'all',
    });
  };

  return (
    <div className="flex items-center justify-between gap-4 mb-4">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5 text-sm text-gray-500">
          <Filter className="w-4 h-4" />
          <span>Filters:</span>
        </div>

        {/* Priority Dropdown */}
        <Select
          value={filters.severity || 'all'}
          onValueChange={handleSeverityChange}
        >
          <SelectTrigger className="w-[130px] h-8 text-xs">
            <SelectValue placeholder="Priority" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All priorities</SelectItem>
            <SelectItem value="urgent">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-tomato" />
                Urgent
              </span>
            </SelectItem>
            <SelectItem value="high">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-yellow-500" />
                High
              </span>
            </SelectItem>
            <SelectItem value="normal">
              <span className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-lime" />
                Normal
              </span>
            </SelectItem>
          </SelectContent>
        </Select>

        {/* Timing Dropdown */}
        <Select
          value={filters.timing || 'all'}
          onValueChange={handleTimingChange}
        >
          <SelectTrigger className="w-[150px] h-8 text-xs">
            <SelectValue placeholder="Timing" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All timing</SelectItem>
            <SelectItem value="today">Due today</SelectItem>
            <SelectItem value="this_week">This week</SelectItem>
            <SelectItem value="next_two_weeks">Next 2 weeks</SelectItem>
          </SelectContent>
        </Select>

        {/* Clear filters button */}
        {hasActiveFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={clearFilters}
            className="h-8 px-2 text-xs text-gray-500 hover:text-gray-700"
          >
            Clear
          </Button>
        )}
      </div>

      <div className="flex items-center gap-3">
        {/* Count display */}
        <span className="text-sm text-gray-500">
          {filteredCount === totalCount ? (
            <>{totalCount} risk{totalCount !== 1 ? 's' : ''}</>
          ) : (
            <>
              {filteredCount} of {totalCount} risk{totalCount !== 1 ? 's' : ''}
            </>
          )}
        </span>

        {/* Refresh button */}
        <Button
          variant="ghost"
          size="sm"
          onClick={onRefresh}
          disabled={isLoading}
          className="h-8 w-8 p-0"
        >
          <RefreshCw
            className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`}
          />
        </Button>
      </div>
    </div>
  );
}
