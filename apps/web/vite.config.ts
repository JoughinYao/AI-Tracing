import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    allowedHosts: ["10.159.3.80", "moonstone-willing-flint.ngrok-free.dev"],
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8100",
        changeOrigin: true,
      },
    },
  },
});
