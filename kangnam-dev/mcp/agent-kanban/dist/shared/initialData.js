import path from "node:path";
import { COLUMN_DEFINITIONS } from "./types.js";
export function createInitialData(cwd) {
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
