import path from "node:path";
import type { KanbanData } from "./types.js";
import { COLUMN_DEFINITIONS } from "./types.js";

export function createInitialData(cwd: string): KanbanData {
  const now = new Date().toISOString();
  const projectName = path.basename(cwd) || "project";
  return {
    version: 1,
    settings: {
      title: "Agent Kanban",
      owner: "Local developer",
      defaultProject: projectName,
      columns: COLUMN_DEFINITIONS
    },
    cards: [],
    sessions: [],
    updatedAt: now
  };
}
