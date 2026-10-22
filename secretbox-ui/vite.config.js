import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  base: '/secretbox/',
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      ['/register', '/login', '/chat', '/coffee-shops', '/menu', '/analytics', '/api', '/health']
        .map((path) => [path, 'http://127.0.0.1:8000']),
    ),
  },
})
