import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Single env file at the repo root (in Docker the vars come from the container env).
  envDir: '..',
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
