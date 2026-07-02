import { defineConfig } from 'astro/config';
import react from '@astrojs/react';

export default defineConfig({
  integrations: [react()],
  vite: {
    server: {
      // Dev convenience: proxy API calls to the brain container.
      proxy: { '/api': 'http://localhost:8300' },
    },
  },
});
