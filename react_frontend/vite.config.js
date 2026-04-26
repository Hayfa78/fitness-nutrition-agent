import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/chat": "http://localhost:8504",
      "/tool": "http://localhost:8504",
      "/api": "http://localhost:8504"
    }
  }
});
