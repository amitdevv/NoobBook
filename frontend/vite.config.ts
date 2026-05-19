import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      src: path.resolve(__dirname, './src'),
    },
  },
  optimizeDeps: {
    include: ['mermaid'],
  },
  ssr: {
    noExternal: ['mermaid'],
  },
  build: {
    rollupOptions: {
      output: {
        // Split pervasive vendor deps out of the eager entry chunk.
        // Only group deps that are used on the dashboard / always-eager paths —
        // lazy-route-only deps are left alone so they stay in their lazy chunks.
        manualChunks(id) {
          if (!id.includes('node_modules')) return
          if (
            /[\\/]node_modules[\\/](react|react-dom|scheduler|react-router|react-router-dom)[\\/]/.test(
              id,
            )
          ) {
            return 'react-vendor'
          }
          if (id.includes('@radix-ui')) return 'radix-vendor'
          if (id.includes('@phosphor-icons')) return 'icons-vendor'
        },
      },
    },
  },
})
