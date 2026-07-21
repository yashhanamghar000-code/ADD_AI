import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  // Pass vite server config nested or directly depending on your plugin version:
  vite: {
    server: {
      allowedHosts: true,
    },
  },
});