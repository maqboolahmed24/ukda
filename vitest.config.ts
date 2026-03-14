import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react(), tsconfigPaths()],
  test: {
    environment: "node",
    include: [
      "packages/**/*.test.ts",
      "packages/**/*.test.tsx",
      "web/**/*.test.ts",
      "web/**/*.test.tsx"
    ]
  }
});
