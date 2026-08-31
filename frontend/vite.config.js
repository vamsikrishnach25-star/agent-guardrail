import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dashboard talks to the FastAPI backend directly over HTTP (CORS is open
// in backend/app/main.py for local dev). No proxy needed - simpler to
// reason about than trying to hide the backend behind Vite's dev proxy.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
});
