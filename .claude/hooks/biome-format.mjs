// PostToolUse hook: run Biome on frontend files Claude edits or writes.
import { spawnSync } from "node:child_process"
import { existsSync, readFileSync } from "node:fs"
import path from "node:path"
import { fileURLToPath } from "node:url"

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..")
const frontendDir = path.join(repoRoot, "frontend")
const exts = new Set([".js", ".jsx", ".ts", ".tsx", ".json", ".css"])

const input = JSON.parse(readFileSync(0, "utf8"))
const filePath = input.tool_response?.filePath ?? input.tool_input?.file_path
if (!filePath) process.exit(0)

const abs = path.resolve(filePath)
const rel = path.relative(frontendDir, abs)
if (rel.startsWith("..") || path.isAbsolute(rel)) process.exit(0)
if (!exts.has(path.extname(abs).toLowerCase())) process.exit(0)

const binDir = path.join(repoRoot, "node_modules", ".bin")
const biome = [path.join(binDir, "biome.exe"), path.join(binDir, "biome")].find(existsSync)
if (!biome) process.exit(0)

const result = spawnSync(
  biome,
  ["check", "--write", "--no-errors-on-unmatched", "--files-ignore-unknown=true", abs],
  { cwd: frontendDir, encoding: "utf8" },
)
// Surface remaining lint errors to Claude without blocking the edit
if (result.status !== 0) {
  process.stderr.write(result.stdout + result.stderr)
  process.exit(2)
}
