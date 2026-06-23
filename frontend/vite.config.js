import { resolve } from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        // Storefront / merchant dashboard (served at "/")
        main: resolve(__dirname, "index.html"),
        // Platform admin console — a separate bundle, served at "/admin"
        admin: resolve(__dirname, "admin.html"),
      },
    },
  },
  server: {
    port: 5173,
    host: true,
    allowedHosts: ['punpay.petgo.asia'],
  },
});
