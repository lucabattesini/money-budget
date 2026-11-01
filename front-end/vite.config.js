import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // Single env file at the repo root (in Docker the vars come from the container env).
  envDir: '..',
})
