/**
 * DesignBootstrapDialog
 *
 * Asks for a few brand-description fields and calls Haiku to draft a starting
 * design.md. The drafted markdown is handed back to the parent (DesignSpecSection)
 * unsaved — the admin reviews and edits in the editor before hitting Save.
 */
import React, { useCallback, useState } from 'react';
import { CircleNotch, Plus, Sparkle, X } from '@phosphor-icons/react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useToast } from '@/components/ui/use-toast';
import { brandAPI } from '@/lib/api/brand';
import { createLogger } from '@/lib/logger';
import { cn } from '@/lib/utils';

const log = createLogger('design-bootstrap');

interface DesignBootstrapDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onResult: (markdown: string) => void;
}

const VIBE_SUGGESTIONS = ['minimal', 'playful', 'enterprise', 'editorial', 'warm', 'technical'];

export const DesignBootstrapDialog: React.FC<DesignBootstrapDialogProps> = ({
  open,
  onOpenChange,
  onResult,
}) => {
  const { error: showError } = useToast();

  const [brandName, setBrandName] = useState('');
  const [industry, setIndustry] = useState('');
  const [primaryColor, setPrimaryColor] = useState('#D97706');
  const [vibeInput, setVibeInput] = useState('');
  const [vibe, setVibe] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);

  const reset = () => {
    setBrandName('');
    setIndustry('');
    setPrimaryColor('#D97706');
    setVibeInput('');
    setVibe([]);
  };

  const addVibe = useCallback((value: string) => {
    const cleaned = value.trim().toLowerCase();
    if (!cleaned) return;
    setVibe((prev) => (prev.includes(cleaned) ? prev : [...prev, cleaned]));
    setVibeInput('');
  }, []);

  const removeVibe = useCallback((value: string) => {
    setVibe((prev) => prev.filter((v) => v !== value));
  }, []);

  const handleSubmit = useCallback(async () => {
    const trimmed = brandName.trim();
    if (!trimmed) {
      showError('Brand name is required');
      return;
    }

    setSubmitting(true);
    try {
      const { data } = await brandAPI.bootstrapDesignMd({
        brand_name: trimmed,
        industry: industry.trim() || undefined,
        vibe: vibe.length ? vibe : undefined,
        primary_color: primaryColor.trim() || undefined,
      });

      if (!data.success) {
        showError(data.error || 'Bootstrap failed');
        return;
      }
      onResult(data.design_md);
      reset();
    } catch (err) {
      log.error({ err }, 'bootstrap call failed');
      showError('Could not draft a spec. Try again.');
    } finally {
      setSubmitting(false);
    }
  }, [brandName, industry, vibe, primaryColor, onResult, showError]);

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && onOpenChange(next)}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-stone-900">
            <Sparkle size={18} weight="fill" className="text-amber-600" />
            Draft a design spec
          </DialogTitle>
          <DialogDescription className="text-stone-600">
            Tell us about the brand. Haiku writes a complete design.md you can edit
            before saving.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-5 py-2">
          <div className="grid gap-1.5">
            <Label htmlFor="bootstrap-brand-name" className="text-stone-700">
              Brand name <span className="text-rose-500">*</span>
            </Label>
            <Input
              id="bootstrap-brand-name"
              value={brandName}
              onChange={(e) => setBrandName(e.target.value)}
              placeholder="e.g. Lumen Studio"
              disabled={submitting}
              autoFocus
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="bootstrap-industry" className="text-stone-700">
              Industry
            </Label>
            <Input
              id="bootstrap-industry"
              value={industry}
              onChange={(e) => setIndustry(e.target.value)}
              placeholder="e.g. SaaS, fintech, education"
              disabled={submitting}
            />
          </div>

          <div className="grid gap-1.5">
            <Label className="text-stone-700">Vibe</Label>
            <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-stone-200 bg-white px-2 py-1.5 focus-within:border-amber-400 focus-within:ring-1 focus-within:ring-amber-200">
              {vibe.map((v) => (
                <span
                  key={v}
                  className="inline-flex items-center gap-1 rounded-full bg-amber-100/70 px-2 py-0.5 text-xs font-medium text-amber-800"
                >
                  {v}
                  <button
                    type="button"
                    onClick={() => removeVibe(v)}
                    disabled={submitting}
                    className="-mr-0.5 text-amber-600 hover:text-amber-900"
                    aria-label={`Remove ${v}`}
                  >
                    <X size={11} weight="bold" />
                  </button>
                </span>
              ))}
              <input
                type="text"
                value={vibeInput}
                onChange={(e) => setVibeInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ',') {
                    e.preventDefault();
                    addVibe(vibeInput);
                  } else if (e.key === 'Backspace' && !vibeInput && vibe.length) {
                    setVibe((prev) => prev.slice(0, -1));
                  }
                }}
                placeholder={vibe.length ? '' : 'minimal, warm, editorial…'}
                disabled={submitting}
                className="min-w-[8rem] flex-1 bg-transparent text-sm text-stone-800 placeholder:text-stone-400 focus:outline-none"
              />
            </div>
            <div className="flex flex-wrap items-center gap-1">
              <span className="text-[11px] text-stone-400">Suggestions:</span>
              {VIBE_SUGGESTIONS.filter((v) => !vibe.includes(v)).slice(0, 5).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => addVibe(v)}
                  disabled={submitting}
                  className="inline-flex items-center gap-0.5 rounded-full border border-stone-200 bg-white px-1.5 py-0.5 text-[11px] text-stone-500 transition-colors hover:border-amber-300 hover:text-amber-800"
                >
                  <Plus size={9} weight="bold" />
                  {v}
                </button>
              ))}
            </div>
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="bootstrap-color" className="text-stone-700">
              Primary color
            </Label>
            <div className="flex items-center gap-2">
              <input
                id="bootstrap-color"
                type="color"
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                disabled={submitting}
                className="h-9 w-12 cursor-pointer rounded-md border border-stone-200 bg-transparent p-0.5"
                aria-label="Primary color"
              />
              <Input
                value={primaryColor}
                onChange={(e) => setPrimaryColor(e.target.value)}
                placeholder="#D97706"
                disabled={submitting}
                className="font-mono"
              />
            </div>
          </div>
        </div>

        <DialogFooter className="flex items-center !justify-between gap-3">
          <p className="text-[11px] text-stone-400">
            Haiku · ~5–10s · costs land in your spend dashboard
          </p>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button
              type="button"
              onClick={handleSubmit}
              disabled={submitting || !brandName.trim()}
              className={cn('bg-amber-600 text-white hover:bg-amber-700', submitting && 'cursor-wait')}
            >
              {submitting ? (
                <>
                  <CircleNotch size={14} className="mr-1.5 animate-spin" />
                  Drafting…
                </>
              ) : (
                <>
                  <Sparkle size={14} className="mr-1.5" weight="fill" />
                  Draft my design.md
                </>
              )}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
