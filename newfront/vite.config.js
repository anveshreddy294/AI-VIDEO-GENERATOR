import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  // Keep React and FastAPI as separate development servers. Browser requests stay
  // same-origin and are forwarded to the backend without weakening FastAPI CORS.
  server: {
    port: 5175,
    host: '0.0.0.0',
    proxy: {
      '/api': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false },
      '/educational-content': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false },
      '/pipeline': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false },
      '/sources': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false },
      '/learning-sessions': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false },
      '/upload': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false },
      '/health': { target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: false }
    }
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor-react': ['react', 'react-dom', 'react-router-dom'],
          'vendor-motion': ['gsap', 'animejs']
        }
      }
    }
  }
});
