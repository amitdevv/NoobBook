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
          // The markdown/syntax-highlight stack (react-markdown + the full
          // refractor grammar set, ~1MB) and the graph-layout libs are only
          // used inside lazy routes (chat / studio / brand settings). Pin them
          // to their own chunks so Rollup doesn't hoist them into the eager
          // entry — keeps first paint small. (Measured: entry 560KB→165KB gz.)
          if (
            /[\\/]node_modules[\\/](refractor|rehype-[^/]+|remark-[^/]+|react-markdown|micromark[^/]*|mdast-[^/]+|hast-[^/]+|@uiw[\\/]react-md(arkdown)?[^/]*|parse5|property-information|character-entities[^/]*|unified|vfile[^/]*|unist-[^/]+)[\\/]/.test(
              id,
            )
          ) {
            return 'markdown-vendor'
          }
          if (/[\\/]node_modules[\\/](dagre|graphlib)[\\/]/.test(id)) {
            return 'graph-vendor'
          }
        },
      },
    },
  },
})
