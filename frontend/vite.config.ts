import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

// The FastAPI server runs on :8000 (`uvicorn portale_von_molthar.entrypoints.api:app`);
// the dev server forwards the API and the game socket so the browser sees one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
});
