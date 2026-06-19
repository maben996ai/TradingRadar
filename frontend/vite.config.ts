import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    host: true,
    port: 3000,
    strictPort: true,
    proxy: {
      "/api": {
        // 默认走 Docker 网络名；宿主机直跑时用 VITE_PROXY_TARGET=http://localhost:8000 覆盖
        target: process.env.VITE_PROXY_TARGET || "http://backend:8000",
        changeOrigin: true,
      },
    },
  },
});
