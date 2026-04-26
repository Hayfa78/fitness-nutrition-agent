import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/chat": {
        target: "https://fitness-nutrition-agent.onrender.com",
        changeOrigin: true
      },
      "/tool": {
        target: "https://fitness-nutrition-agent.onrender.com",
        changeOrigin: true
      },
      "/api": {
        target: "https://fitness-nutrition-agent.onrender.com",
        changeOrigin: true
      }
    }
  }
});
