import { mkdir, mkdtemp, writeFile, rm } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { afterEach, describe, expect, it } from "vitest";
import { resolveProjectDataPath, resolveProjectRoot } from "../src/shared/projectPaths.js";

const originalDataPath = process.env.KANBAN_DATA_PATH;

afterEach(() => {
  if (originalDataPath === undefined) {
    delete process.env.KANBAN_DATA_PATH;
  } else {
    process.env.KANBAN_DATA_PATH = originalDataPath;
  }
});

describe("project path resolution", () => {
  it("routes nested cwd values to the project-local .kanban data file", async () => {
    const dir = await mkdtemp(path.join(tmpdir(), "agent-kanban-project-"));
    try {
      await writeFile(path.join(dir, "package.json"), "{\"name\":\"demo\"}\n", "utf8");
      const nested = path.join(dir, "src", "server");
      await mkdir(nested, { recursive: true });

      expect(resolveProjectRoot(nested)).toBe(dir);
      expect(resolveProjectDataPath(nested)).toBe(path.join(dir, ".kanban", "kanban-data.json"));
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("keeps KANBAN_DATA_PATH as an explicit override", async () => {
    const dir = await mkdtemp(path.join(tmpdir(), "agent-kanban-override-"));
    try {
      const override = path.join(dir, "custom.json");
      process.env.KANBAN_DATA_PATH = override;
      expect(resolveProjectDataPath(dir)).toBe(override);
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
