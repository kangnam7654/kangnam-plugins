import { existsSync, statSync } from "node:fs";
import path from "node:path";

const PROJECT_MARKERS = [".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod", "AGENTS.md"];

export function resolveProjectRoot(cwd = process.cwd()): string {
  let current = path.resolve(cwd);
  if (existsSync(current)) {
    const stat = statSync(current);
    if (!stat.isDirectory()) current = path.dirname(current);
  }

  while (true) {
    if (PROJECT_MARKERS.some((marker) => existsSync(path.join(current, marker)))) {
      return current;
    }

    const parent = path.dirname(current);
    if (parent === current) return path.resolve(cwd);
    current = parent;
  }
}

export function resolveProjectDataPath(cwd = process.cwd()): string {
  if (process.env.KANBAN_DATA_PATH) return path.resolve(process.env.KANBAN_DATA_PATH);
  return path.join(resolveProjectRoot(cwd), ".kanban", "kanban-data.json");
}
