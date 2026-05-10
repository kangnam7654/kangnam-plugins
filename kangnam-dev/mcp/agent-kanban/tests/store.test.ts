import { mkdtemp, rm } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import { describe, expect, it } from "vitest";
import { KanbanStore } from "../src/shared/store.js";

async function testStore(): Promise<{ store: KanbanStore; dir: string }> {
  const dir = await mkdtemp(path.join(tmpdir(), "agent-kanban-"));
  return { store: new KanbanStore(path.join(dir, "board.json")), dir };
}

describe("KanbanStore", () => {
  it("creates initial board data when no file exists", async () => {
    const { store, dir } = await testStore();
    try {
      const board = await store.getBoard();
      expect(board.cards).toEqual([]);
      expect(board.settings.columns.map((column) => column.id)).toContain("in_progress");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("supports the agent workflow from create to complete", async () => {
    const { store, dir } = await testStore();
    try {
      const created = await store.createCard({
        title: "Add persistent MCP workflow",
        status: "ready",
        priority: "high",
        cwd: "/workspace/demo",
        branch: "feature/kanban",
        tags: ["mcp"],
        nextAction: "Claim and implement."
      });

      const session = await store.startSession({
        agentSessionId: "session-1",
        cwd: "/workspace/demo",
        branch: "feature/kanban"
      });
      expect(session.context.recommendedCards.some((card) => card.id === created.id)).toBe(true);

      const claimed = await store.claimCard({
        cardId: created.id,
        agentSessionId: "session-1",
        cwd: "/workspace/demo",
        branch: "feature/kanban"
      });
      expect(claimed.status).toBe("in_progress");
      expect(claimed.assignee.sessionId).toBe("session-1");

      const progressed = await store.appendProgress({
        cardId: created.id,
        message: "Implemented store API.",
        filesTouched: ["src/shared/store.ts"],
        nextAction: "Run tests.",
        test: {
          command: "npm test",
          status: "passed",
          summary: "Store tests passed."
        }
      });
      expect(progressed.filesTouched).toEqual(["src/shared/store.ts"]);
      expect(progressed.tests.at(-1)?.status).toBe("passed");

      const completed = await store.completeCard({
        cardId: created.id,
        summary: "Verified and complete.",
        tests: [{ command: "npm test", status: "passed", summary: "Regression passed." }]
      });
      expect(completed.status).toBe("done");
      expect(completed.completedAt).toBeDefined();
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("captures blockers with concrete next actions", async () => {
    const { store, dir } = await testStore();
    try {
      const card = await store.createCard({ title: "Choose auth model", status: "ready" });
      const blocked = await store.blockCard({
        cardId: card.id,
        reason: "Need user decision on local-only versus remote multi-user mode.",
        nextAction: "Ask for deployment target."
      });
      expect(blocked.status).toBe("blocked");
      expect(blocked.blockers[0]?.reason).toContain("Need user decision");
      expect(blocked.nextAction).toBe("Ask for deployment target.");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });
});
