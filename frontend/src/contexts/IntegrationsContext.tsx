import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import {
  databasesAPI,
  googleDriveAPI,
  mcpAPI,
  type DatabaseConnection,
  type GoogleStatus,
  type McpConnection,
} from '@/lib/api/settings';
import { createLogger } from '@/lib/logger';
import { patchOne, removeOne, upsertOne } from '@/lib/resourceState';

const log = createLogger('integrations-context');

interface IntegrationsContextValue {
  googleStatus: GoogleStatus;
  googleLoaded: boolean;
  googleLoading: boolean;
  dbConnections: DatabaseConnection[];
  dbLoaded: boolean;
  dbLoading: boolean;
  mcpConnections: McpConnection[];
  mcpLoaded: boolean;
  mcpLoading: boolean;
  ensureGoogleStatus: (options?: { force?: boolean; silent?: boolean }) => Promise<GoogleStatus>;
  ensureDatabases: (options?: { force?: boolean; silent?: boolean }) => Promise<DatabaseConnection[]>;
  ensureMcpConnections: (options?: { force?: boolean; silent?: boolean }) => Promise<McpConnection[]>;
  setGoogleStatus: React.Dispatch<React.SetStateAction<GoogleStatus>>;
  upsertDatabase: (database: DatabaseConnection) => void;
  removeDatabase: (id: string) => void;
  patchDatabase: (id: string, updates: Partial<DatabaseConnection>) => void;
  upsertMcpConnection: (connection: McpConnection) => void;
  removeMcpConnection: (id: string) => void;
  patchMcpConnection: (id: string, updates: Partial<McpConnection>) => void;
}

const DEFAULT_GOOGLE_STATUS: GoogleStatus = {
  configured: false,
  connected: false,
  email: null,
};

const IntegrationsContext = createContext<IntegrationsContextValue | null>(null);

export const IntegrationsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [googleStatus, setGoogleStatus] = useState<GoogleStatus>(DEFAULT_GOOGLE_STATUS);
  const [googleLoaded, setGoogleLoaded] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [dbConnections, setDbConnections] = useState<DatabaseConnection[]>([]);
  const [dbLoaded, setDbLoaded] = useState(false);
  const [dbLoading, setDbLoading] = useState(false);
  const [mcpConnections, setMcpConnections] = useState<McpConnection[]>([]);
  const [mcpLoaded, setMcpLoaded] = useState(false);
  const [mcpLoading, setMcpLoading] = useState(false);

  const ensureGoogleStatus = useCallback(async (options?: { force?: boolean; silent?: boolean }) => {
    const { force = false, silent = false } = options ?? {};
    if (googleLoaded && !force) {
      return googleStatus;
    }

    if (!silent) setGoogleLoading(true);
    try {
      const status = await googleDriveAPI.getStatus();
      setGoogleStatus(status);
      setGoogleLoaded(true);
      return status;
    } catch (err) {
      log.error({ err }, 'failed to load Google status');
      throw err;
    } finally {
      if (!silent) setGoogleLoading(false);
    }
  }, [googleLoaded, googleStatus]);

  const ensureDatabases = useCallback(async (options?: { force?: boolean; silent?: boolean }) => {
    const { force = false, silent = false } = options ?? {};
    if (dbLoaded && !force) {
      return dbConnections;
    }

    if (!silent) setDbLoading(true);
    try {
      const databases = await databasesAPI.listDatabases();
      setDbConnections(databases);
      setDbLoaded(true);
      return databases;
    } catch (err) {
      log.error({ err }, 'failed to load databases');
      throw err;
    } finally {
      if (!silent) setDbLoading(false);
    }
  }, [dbConnections, dbLoaded]);

  const ensureMcpConnections = useCallback(async (options?: { force?: boolean; silent?: boolean }) => {
    const { force = false, silent = false } = options ?? {};
    if (mcpLoaded && !force) {
      return mcpConnections;
    }

    if (!silent) setMcpLoading(true);
    try {
      const connections = await mcpAPI.listConnections();
      setMcpConnections(connections);
      setMcpLoaded(true);
      return connections;
    } catch (err) {
      log.error({ err }, 'failed to load MCP connections');
      throw err;
    } finally {
      if (!silent) setMcpLoading(false);
    }
  }, [mcpConnections, mcpLoaded]);

  const value = useMemo<IntegrationsContextValue>(() => ({
    googleStatus,
    googleLoaded,
    googleLoading,
    dbConnections,
    dbLoaded,
    dbLoading,
    mcpConnections,
    mcpLoaded,
    mcpLoading,
    ensureGoogleStatus,
    ensureDatabases,
    ensureMcpConnections,
    setGoogleStatus,
    upsertDatabase: (database) => setDbConnections((prev) => upsertOne(prev, database, { prepend: true })),
    removeDatabase: (id) => setDbConnections((prev) => removeOne(prev, id)),
    patchDatabase: (id, updates) => setDbConnections((prev) => patchOne(prev, id, updates)),
    upsertMcpConnection: (connection) => setMcpConnections((prev) => upsertOne(prev, connection, { prepend: true })),
    removeMcpConnection: (id) => setMcpConnections((prev) => removeOne(prev, id)),
    patchMcpConnection: (id, updates) => setMcpConnections((prev) => patchOne(prev, id, updates)),
  }), [
    dbConnections,
    dbLoaded,
    dbLoading,
    ensureDatabases,
    ensureGoogleStatus,
    ensureMcpConnections,
    googleLoaded,
    googleLoading,
    googleStatus,
    mcpConnections,
    mcpLoaded,
    mcpLoading,
  ]);

  return (
    <IntegrationsContext.Provider value={value}>
      {children}
    </IntegrationsContext.Provider>
  );
};

// eslint-disable-next-line react-refresh/only-export-components
export const useIntegrations = () => {
  const context = useContext(IntegrationsContext);
  if (!context) {
    throw new Error('useIntegrations must be used within IntegrationsProvider');
  }
  return context;
};
