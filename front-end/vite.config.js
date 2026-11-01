import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Single env file at the repo root (in Docker the vars come from the container env).
  envDir: '..',
  build: {
    rollupOptions: {
      output: {
        // Keep the big libraries in their own files so the app code is small and cacheable
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/node_modules\/(recharts|d3-[^/]+|victory-vendor|@chakra-ui\/charts)\//.test(id)) return 'charts'
          if (/node_modules\/(@chakra-ui|@ark-ui|@zag-js|@emotion|@floating-ui|next-themes)\//.test(id)) return 'chakra'
          if (/node_modules\/(react|react-dom|react-router|react-router-dom|scheduler)\//.test(id)) return 'react'
          return undefined
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx}'],
    // Fixed values, so a developer's own .env can never change test results
    env: {
      VITE_API_URL: 'http://api.test',
      VITE_GOOGLE_CLIENT_ID: 'test-google-client-id',
    },
  },
})
