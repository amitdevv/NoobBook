import { createContext } from 'react';
import type { StudioSignal, StudioItemId } from './types';

export interface StudioContextValue {
  projectId: string;
  signals: StudioSignal[];
  validSourceIds: Set<string>;
  pickerOpen: boolean;
  setPickerOpen: (open: boolean) => void;
  selectedItem: StudioItemId | null;
  selectedSignals: StudioSignal[];
  triggerGeneration: (optionId: StudioItemId, signal: StudioSignal) => void;
  registerGenerationHandler: (itemId: StudioItemId, handler: (signal: StudioSignal) => Promise<void>) => void;
  handleGenerate: (optionId: StudioItemId, itemSignals: StudioSignal[]) => void;
  getItemTitle: (itemId: StudioItemId) => string;
  getItemIcon: (itemId: StudioItemId) => React.ComponentType<{ size?: number; className?: string }> | undefined;
}

export const StudioContext = createContext<StudioContextValue | null>(null);
