import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const webRoot = resolve(repoRoot, "web");
const pythonCandidates = [
  resolve(webRoot, ".venv", "Scripts", "python.exe"),
  resolve(webRoot, ".venv", "bin", "python"),
  process.env.PYTHON,
  "python",
  "python3",
].filter(Boolean);

let python;
for (const candidate of pythonCandidates) {
  if (candidate.includes(resolve(repoRoot)) && !existsSync(candidate)) continue;
  const probe = spawnSync(candidate, ["--version"], { cwd: webRoot, stdio: "ignore" });
  if (!probe.error && probe.status === 0) {
    python = candidate;
    break;
  }
}

if (!python) {
  console.error("Python was not found. Create web/.venv and install web/requirements.txt.");
  process.exit(1);
}

for (const args of [["manage.py", "check"], ["manage.py", "collectstatic", "--noinput"]]) {
  const result = spawnSync(python, args, { cwd: webRoot, stdio: "inherit" });
  if (result.error) {
    console.error(`Could not run Python: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}
