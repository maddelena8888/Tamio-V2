/**
 * StructuredResponse - Enhanced TAMI chat response rendering
 *
 * Features:
 * - Parses markdown into structured sections
 * - Collapsible sections for detailed information
 * - Styled action items and recommendations
 * - Key numbers highlighted in cards
 */

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { ChevronDown, ChevronRight, Lightbulb, AlertCircle, TrendingUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

// ============================================================================
// Types
// ============================================================================

interface Section {
  type: 'summary' | 'details' | 'recommendations' | 'warning' | 'numbers';
  title?: string;
  content: string;
  items?: string[];
}

interface StructuredResponseProps {
  content: string;
  className?: string;
}

// ============================================================================
// Parsing Logic
// ============================================================================

/**
 * Parse markdown content into structured sections for enhanced display.
 *
 * Detects:
 * - Summary: First paragraph(s) before any headers
 * - Details: ## headers become collapsible sections
 * - Recommendations: Lines starting with "- " after recommendation keywords
 * - Warnings: Content after warning markers
 * - Numbers: Key financial figures
 */
function parseContentIntoSections(content: string): Section[] {
  const sections: Section[] = [];
  const lines = content.split('\n');

  let currentSection: Section = { type: 'summary', content: '' };
  let inRecommendations = false;
  let recommendationItems: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmedLine = line.trim();

    // Check for headers (## or ###)
    if (trimmedLine.startsWith('## ') || trimmedLine.startsWith('### ')) {
      // Save current section
      if (currentSection.content.trim() || (currentSection.items && currentSection.items.length > 0)) {
        if (inRecommendations && recommendationItems.length > 0) {
          currentSection.items = recommendationItems;
          recommendationItems = [];
        }
        sections.push(currentSection);
      }

      const title = trimmedLine.replace(/^#{2,3}\s+/, '');

      // Detect section type from title
      const lowerTitle = title.toLowerCase();
      if (lowerTitle.includes('recommend') || lowerTitle.includes('next step') || lowerTitle.includes('action')) {
        currentSection = { type: 'recommendations', title, content: '', items: [] };
        inRecommendations = true;
      } else if (lowerTitle.includes('warning') || lowerTitle.includes('risk') || lowerTitle.includes('concern')) {
        currentSection = { type: 'warning', title, content: '' };
        inRecommendations = false;
      } else if (lowerTitle.includes('number') || lowerTitle.includes('metric') || lowerTitle.includes('summary')) {
        currentSection = { type: 'numbers', title, content: '' };
        inRecommendations = false;
      } else {
        currentSection = { type: 'details', title, content: '' };
        inRecommendations = false;
      }
      continue;
    }

    // Check for recommendation list items
    if (inRecommendations && trimmedLine.startsWith('- ')) {
      recommendationItems.push(trimmedLine.slice(2));
      continue;
    }

    // Check for standalone recommendation markers
    if (trimmedLine.toLowerCase().includes('recommend') && trimmedLine.includes(':')) {
      if (currentSection.content.trim()) {
        sections.push(currentSection);
      }
      currentSection = { type: 'recommendations', title: 'Recommendations', content: '', items: [] };
      inRecommendations = true;
      continue;
    }

    // Add line to current section
    currentSection.content += line + '\n';
  }

  // Save final section
  if (currentSection.content.trim() || (currentSection.items && currentSection.items.length > 0)) {
    if (inRecommendations && recommendationItems.length > 0) {
      currentSection.items = recommendationItems;
    }
    sections.push(currentSection);
  }

  return sections;
}

// ============================================================================
// Sub-components
// ============================================================================

function SummarySection({ content }: { content: string }) {
  return (
    <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-1.5 text-sm">
      <ReactMarkdown>{content.trim()}</ReactMarkdown>
    </div>
  );
}

function DetailsSection({ title, content }: { title: string; content: string }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} className="mt-3">
      <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium text-gunmetal/70 hover:text-gunmetal transition-colors w-full text-left py-1">
        {isOpen ? (
          <ChevronDown className="w-4 h-4 flex-shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 flex-shrink-0" />
        )}
        <span>{title}</span>
      </CollapsibleTrigger>
      <CollapsibleContent className="pl-6 pt-2">
        <div className="prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-1 text-sm text-gunmetal/80">
          <ReactMarkdown>{content.trim()}</ReactMarkdown>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function RecommendationsSection({ title, content, items }: { title?: string; content: string; items?: string[] }) {
  return (
    <div className="mt-3 p-3 rounded-lg bg-lime/10 border border-lime/30">
      <div className="flex items-center gap-2 mb-2">
        <Lightbulb className="w-4 h-4 text-lime-700" />
        <h4 className="text-xs font-semibold uppercase tracking-wide text-lime-700">
          {title || 'Recommendations'}
        </h4>
      </div>
      {items && items.length > 0 ? (
        <ul className="space-y-1.5">
          {items.map((item, idx) => (
            <li key={idx} className="text-sm text-gunmetal flex items-start gap-2">
              <span className="text-lime-600 mt-0.5 flex-shrink-0">•</span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : content.trim() ? (
        <div className="prose prose-sm max-w-none text-gunmetal">
          <ReactMarkdown>{content.trim()}</ReactMarkdown>
        </div>
      ) : null}
    </div>
  );
}

function WarningSection({ title, content }: { title?: string; content: string }) {
  return (
    <div className="mt-3 p-3 rounded-lg bg-yellow-50 border border-yellow-200">
      <div className="flex items-center gap-2 mb-2">
        <AlertCircle className="w-4 h-4 text-yellow-700" />
        <h4 className="text-xs font-semibold uppercase tracking-wide text-yellow-700">
          {title || 'Warning'}
        </h4>
      </div>
      <div className="prose prose-sm max-w-none text-yellow-900">
        <ReactMarkdown>{content.trim()}</ReactMarkdown>
      </div>
    </div>
  );
}

function NumbersSection({ title, content }: { title?: string; content: string }) {
  return (
    <div className="mt-3 p-3 rounded-lg bg-blue-50 border border-blue-200">
      <div className="flex items-center gap-2 mb-2">
        <TrendingUp className="w-4 h-4 text-blue-700" />
        <h4 className="text-xs font-semibold uppercase tracking-wide text-blue-700">
          {title || 'Key Numbers'}
        </h4>
      </div>
      <div className="prose prose-sm max-w-none text-blue-900">
        <ReactMarkdown>{content.trim()}</ReactMarkdown>
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function StructuredResponse({ content, className }: StructuredResponseProps) {
  // If content is short or simple, just render as markdown
  if (content.length < 200 && !content.includes('##') && !content.includes('- ')) {
    return (
      <div className={cn("prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-1.5 text-sm", className)}>
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }

  const sections = parseContentIntoSections(content);

  // If parsing didn't produce meaningful sections, fall back to plain markdown
  if (sections.length === 1 && sections[0].type === 'summary') {
    return (
      <div className={cn("prose prose-sm dark:prose-invert max-w-none prose-p:leading-relaxed prose-p:my-1.5 text-sm", className)}>
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {sections.map((section, idx) => {
        switch (section.type) {
          case 'summary':
            return <SummarySection key={idx} content={section.content} />;
          case 'details':
            return <DetailsSection key={idx} title={section.title || 'Details'} content={section.content} />;
          case 'recommendations':
            return <RecommendationsSection key={idx} title={section.title} content={section.content} items={section.items} />;
          case 'warning':
            return <WarningSection key={idx} title={section.title} content={section.content} />;
          case 'numbers':
            return <NumbersSection key={idx} title={section.title} content={section.content} />;
          default:
            return <SummarySection key={idx} content={section.content} />;
        }
      })}
    </div>
  );
}

export default StructuredResponse;
