import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { brandAPI, type BrandConfig } from '@/lib/api/brand';
import { createLogger } from '@/lib/logger';

const log = createLogger('brand-config-context');

interface BrandConfigContextValue {
  config: BrandConfig | null;
  initialLoading: boolean;
  refreshConfig: (options?: { silent?: boolean; force?: boolean }) => Promise<BrandConfig | null>;
  patchConfig: (updates: Partial<BrandConfig>) => void;
}

const BrandConfigContext = createContext<BrandConfigContextValue | null>(null);

export const BrandConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<BrandConfig | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);

  const refreshConfig = useCallback(async (options?: { silent?: boolean; force?: boolean }) => {
    const { silent = false, force = false } = options ?? {};
    if (loaded && !force) {
      return config;
    }

    if (!silent) {
      setInitialLoading(true);
    }

    try {
      const response = await brandAPI.getConfig();
      const nextConfig = response.data.success ? response.data.config : null;
      setConfig(nextConfig);
      setLoaded(true);
      return nextConfig;
    } catch (err) {
      log.error({ err }, 'failed to load brand config');
      throw err;
    } finally {
      if (!silent) {
        setInitialLoading(false);
      }
    }
  }, [config, loaded]);

  useEffect(() => {
    refreshConfig().catch(() => {
      setInitialLoading(false);
    });
  }, [refreshConfig]);

  const value = useMemo<BrandConfigContextValue>(() => ({
    config,
    initialLoading,
    refreshConfig,
    patchConfig: (updates) => {
      setConfig((prev) => (prev ? { ...prev, ...updates } : prev));
    },
  }), [config, initialLoading, refreshConfig]);

  return (
    <BrandConfigContext.Provider value={value}>
      {children}
    </BrandConfigContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useBrandConfig = () => {
  const context = useContext(BrandConfigContext);
  if (!context) {
    throw new Error('useBrandConfig must be used within BrandConfigProvider');
  }
  return context;
};
