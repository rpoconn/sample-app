import { createRequire } from "node:module"
import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import { tanstackRouter } from "@tanstack/router-plugin/vite"
import react from "@vitejs/plugin-react-swc"
import { defineConfig } from "vite"

// https://vitejs.dev/config/
export default defineConfig({
    build: {
        outDir: "../backend/app/frontend",
        emptyOutDir: true,
    },
    resolve: {
        alias: {
            "@": path.resolve(import.meta.dirname, "./src"),
            // Bun may hoist the package to the workspace root; import.meta.glob needs a real path
            "@region-flags": path.dirname(
                createRequire(import.meta.url).resolve(
                    "region-flags/package.json",
                ),
            ),
        },
    },
    plugins: [
        tanstackRouter({
            target: "react",
            autoCodeSplitting: true,
        }),
        react(),
        tailwindcss(),
    ],
})
