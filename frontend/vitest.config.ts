/**
 * Vitest config — extends the existing vite.config.ts so path aliases
 * (`@/*`), the React plugin, and any future Vite tweaks are honoured by
 * the test runner too.
 *
 * happy-dom is used over jsdom because it's noticeably faster to start
 * and we don't need any of jsdom's quirkier (mostly Selenium-style) API
 * coverage. We test browser-API boundaries (BroadcastChannel, localStorage,
 * window event listeners) so happy-dom's coverage is more than sufficient.
 */
import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'happy-dom',
      globals: false,
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
    },
  }),
);
