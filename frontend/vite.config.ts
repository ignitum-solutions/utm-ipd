import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react(), {
    name: 'build-revision',
    transformIndexHtml: () => [{
      tag: 'meta',
      attrs: { name: 'utm-build-revision', content: process.env.VITE_BUILD_REVISION ?? 'local' },
      injectTo: 'head',
    }],
  }],
  server: {
    port: 5173,
    strictPort: true,
    proxy: { '/api': { target: process.env.UTM_API_TARGET ?? 'http://127.0.0.1:8000' } },
  },
});
