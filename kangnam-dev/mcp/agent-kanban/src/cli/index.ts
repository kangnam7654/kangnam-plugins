#!/usr/bin/env node
import { KanbanStore, KanbanStoreError } from "../shared/store.js";
import { resolveProjectDataPath, resolveProjectRoot } from "../shared/projectPaths.js";
import type {
  AppendProgressInput,
  CardFilters,
  CardStatus,
  KanbanCard,
  PaginatedCards,
  Priority,
  TestStatus
} from "../shared/types.js";

type Flags = Record<string, string | boolean>;

interface ParsedArgs {
  command: string;
  positionals: string[];
  flags: Flags;
}

const HELP = `agent-kanban: project-local Kanban for LLM development sessions

Usage:
  agent-kanban context --cwd <path> [--branch <name>] [--json]
  agent-kanban start --cwd <path> [--branch <name>] [--session <id>]
  agent-kanban list --cwd <path> [--status ready] [--json]
  agent-kanban create "Title" --cwd <path> [--priority high] [--status ready] [--tags api,ui] [--next "..."]
  agent-kanban claim <card-id> --cwd <path> --session <id>
  agent-kanban move <card-id> <status> --cwd <path>
  agent-kanban progress <card-id> --cwd <path> --msg "..." [--files a,b] [--next "..."] [--test-command "..."] [--test-status passed] [--test-summary "..."]
  agent-kanban block <card-id> --cwd <path> --reason "..." [--next "..."]
  agent-kanban done <card-id> --cwd <path> --summary "..." [--test-command "..."] [--test-status passed] [--test-summary "..."]
  agent-kanban end --cwd <path> --session <id> --outcome completed --summary "..."
  agent-kanban path --cwd <path>

Data:
  Default board path is <project-root>/.kanban/kanban-data.json.
  KANBAN_DATA_PATH remains available as an explicit override for tests or special shared boards.
`;

async function main(): Promise<void> {
  const parsed = parseArgs(process.argv.slice(2));
  if (!parsed.command || parsed.flags.help || parsed.flags.h) {
    write(HELP);
    return;
  }

  const cwd = stringFlag(parsed.flags, "cwd") ?? process.cwd();
  const store = KanbanStore.forCwd(cwd);
  const json = Boolean(parsed.flags.json) || stringFlag(parsed.flags, "format") === "json";

  switch (parsed.command) {
    case "context":
      await contextCommand(store, parsed.flags, cwd, json);
      break;
    case "start":
      await startCommand(store, parsed.flags, cwd, json);
      break;
    case "list":
      await listCommand(store, parsed.flags, json);
      break;
    case "create":
    case "new":
      await createCommand(store, parsed, cwd, json);
      break;
    case "claim":
      await claimCommand(store, parsed, cwd, json);
      break;
    case "move":
      await moveCommand(store, parsed, cwd, json);
      break;
    case "progress":
      await progressCommand(store, parsed, cwd, json);
      break;
    case "block":
      await blockCommand(store, parsed, cwd, json);
      break;
    case "done":
    case "complete":
      await doneCommand(store, parsed, cwd, json);
      break;
    case "end":
      await endCommand(store, parsed, cwd, json);
      break;
    case "path":
      write(resolveProjectDataPath(cwd));
      break;
    default:
      throw new KanbanStoreError(`Unknown command '${parsed.command}'. Run agent-kanban --help.`);
  }
}

async function contextCommand(store: KanbanStore, flags: Flags, cwd: string, json: boolean): Promise<void> {
  const context = await store.getContext({
    cwd,
    branch: stringFlag(flags, "branch"),
    agentSessionId: stringFlag(flags, "session") ?? stringFlag(flags, "agent-session-id"),
    includeDone: Boolean(flags["include-done"]),
    limit: numberFlag(flags, "limit") ?? 10
  });
  write(json ? JSON.stringify(context, null, 2) : compactContext(context.guidance, context.activeCards, context.recommendedCards, context.blockedCards, context.reviewCards));
}

async function startCommand(store: KanbanStore, flags: Flags, cwd: string, json: boolean): Promise<void> {
  const output = await store.startSession({
    cwd,
    agentSessionId: stringFlag(flags, "session"),
    branch: stringFlag(flags, "branch"),
    focus: stringFlag(flags, "focus")
  });
  write(json ? JSON.stringify(output, null, 2) : [`session ${output.session.id}`, compactContext(output.context.guidance, output.context.activeCards, output.context.recommendedCards, output.context.blockedCards, output.context.reviewCards)].join("\n"));
}

async function listCommand(store: KanbanStore, flags: Flags, json: boolean): Promise<void> {
  const filters: CardFilters = {
    status: stringFlag(flags, "status") as CardStatus | undefined,
    branch: stringFlag(flags, "branch"),
    tag: stringFlag(flags, "tag"),
    query: stringFlag(flags, "query"),
    includeDone: Boolean(flags["include-done"]),
    limit: numberFlag(flags, "limit") ?? 50,
    offset: numberFlag(flags, "offset") ?? 0
  };
  const page = await store.listCards(filters);
  write(json ? JSON.stringify(page, null, 2) : compactPage(page));
}

async function createCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const title = stringFlag(parsed.flags, "title") ?? parsed.positionals.join(" ").trim();
  if (!title) throw new KanbanStoreError("title is required.");
  const card = await store.createCard({
    title,
    cwd,
    branch: stringFlag(parsed.flags, "branch"),
    description: stringFlag(parsed.flags, "desc") ?? stringFlag(parsed.flags, "description"),
    status: (stringFlag(parsed.flags, "status") as CardStatus | undefined) ?? "backlog",
    priority: (stringFlag(parsed.flags, "priority") as Priority | undefined) ?? "medium",
    tags: csvFlag(parsed.flags, "tags"),
    nextAction: stringFlag(parsed.flags, "next")
  });
  write(json ? JSON.stringify(card, null, 2) : compactCard(card));
}

async function claimCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const cardId = requirePositional(parsed, 0, "card-id");
  const sessionId = stringFlag(parsed.flags, "session") ?? process.env.AGENT_SESSION_ID ?? `cli-${Date.now()}`;
  const card = await store.claimCard({
    cardId,
    cwd,
    agentSessionId: sessionId,
    branch: stringFlag(parsed.flags, "branch"),
    note: stringFlag(parsed.flags, "note")
  });
  write(json ? JSON.stringify(card, null, 2) : compactCard(card));
}

async function moveCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const cardId = requirePositional(parsed, 0, "card-id");
  const status = requirePositional(parsed, 1, "status") as CardStatus;
  const card = await store.moveCard({ cardId, cwd, status, note: stringFlag(parsed.flags, "note") });
  write(json ? JSON.stringify(card, null, 2) : compactCard(card));
}

async function progressCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const cardId = requirePositional(parsed, 0, "card-id");
  const message = stringFlag(parsed.flags, "msg") ?? stringFlag(parsed.flags, "message");
  if (!message) throw new KanbanStoreError("--msg is required.");
  const input: AppendProgressInput = {
    cardId,
    cwd,
    message,
    filesTouched: csvFlag(parsed.flags, "files"),
    nextAction: stringFlag(parsed.flags, "next"),
    test: testFromFlags(parsed.flags)
  };
  const card = await store.appendProgress(input);
  write(json ? JSON.stringify(card, null, 2) : compactCard(card));
}

async function blockCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const cardId = requirePositional(parsed, 0, "card-id");
  const reason = stringFlag(parsed.flags, "reason");
  if (!reason) throw new KanbanStoreError("--reason is required.");
  const card = await store.blockCard({ cardId, cwd, reason, nextAction: stringFlag(parsed.flags, "next") });
  write(json ? JSON.stringify(card, null, 2) : compactCard(card));
}

async function doneCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const cardId = requirePositional(parsed, 0, "card-id");
  const summary = stringFlag(parsed.flags, "summary");
  if (!summary) throw new KanbanStoreError("--summary is required.");
  const test = testFromFlags(parsed.flags);
  const card = await store.completeCard({ cardId, cwd, summary, tests: test ? [test] : [] });
  write(json ? JSON.stringify(card, null, 2) : compactCard(card));
}

async function endCommand(store: KanbanStore, parsed: ParsedArgs, cwd: string, json: boolean): Promise<void> {
  const agentSessionId = stringFlag(parsed.flags, "session");
  const outcome = stringFlag(parsed.flags, "outcome");
  const summary = stringFlag(parsed.flags, "summary");
  if (!agentSessionId) throw new KanbanStoreError("--session is required.");
  if (!outcome) throw new KanbanStoreError("--outcome is required.");
  if (!summary) throw new KanbanStoreError("--summary is required.");
  const session = await store.endSession({
    cwd,
    agentSessionId,
    outcome: outcome as "continued" | "blocked" | "completed" | "abandoned",
    summary,
    nextAction: stringFlag(parsed.flags, "next")
  });
  write(json ? JSON.stringify(session, null, 2) : `session ${session.id} ${session.outcome}: ${session.summary}`);
}

function compactContext(guidance: string[], active: KanbanCard[], ready: KanbanCard[], blocked: KanbanCard[], review: KanbanCard[]): string {
  return [
    `counts active=${active.length} ready=${ready.length} blocked=${blocked.length} review=${review.length}`,
    ...guidance.map((item) => `guide ${item}`),
    ...active.slice(0, 8).map((card) => `active ${compactCard(card)}`),
    ...ready.slice(0, 8).map((card) => `ready ${compactCard(card)}`),
    ...blocked.slice(0, 8).map((card) => `blocked ${compactCard(card)}`),
    ...review.slice(0, 8).map((card) => `review ${compactCard(card)}`)
  ].join("\n");
}

function compactPage(page: PaginatedCards): string {
  return [`cards total=${page.total} count=${page.count} offset=${page.offset}${page.hasMore ? ` next=${page.nextOffset}` : ""}`, ...page.cards.map(compactCard)].join("\n");
}

function compactCard(card: KanbanCard): string {
  const parts = [
    card.id,
    `status=${card.status}`,
    `priority=${card.priority}`,
    `title=${quote(card.title)}`,
    card.branch ? `branch=${quote(card.branch)}` : "",
    card.nextAction ? `next=${quote(card.nextAction)}` : "",
    card.filesTouched.length ? `files=${card.filesTouched.join(",")}` : "",
    card.tests.length ? `test=${card.tests.at(-1)?.status}` : "",
    card.blockers.some((blocker) => !blocker.resolvedAt) ? `blocked=${card.blockers.filter((blocker) => !blocker.resolvedAt).length}` : ""
  ];
  return parts.filter(Boolean).join(" ");
}

function testFromFlags(flags: Flags): { command: string; status: TestStatus; summary: string } | undefined {
  const command = stringFlag(flags, "test-command");
  const status = (stringFlag(flags, "test-status") as TestStatus | undefined) ?? "passed";
  const summary = stringFlag(flags, "test-summary");
  if (!command && !summary) return undefined;
  if (!command || !summary) throw new KanbanStoreError("--test-command and --test-summary must be provided together.");
  return { command, status, summary };
}

function parseArgs(argv: string[]): ParsedArgs {
  const [command = "", ...rest] = argv;
  const flags: Flags = {};
  const positionals: string[] = [];

  for (let index = 0; index < rest.length; index += 1) {
    const arg = rest[index];
    if (!arg) continue;
    if (!arg.startsWith("--")) {
      positionals.push(arg);
      continue;
    }

    const raw = arg.slice(2);
    const [key, inlineValue] = raw.split(/=(.*)/s).filter((item) => item !== undefined);
    if (!key) continue;
    if (inlineValue !== undefined) {
      flags[key] = inlineValue;
      continue;
    }

    const next = rest[index + 1];
    if (next && !next.startsWith("--")) {
      flags[key] = next;
      index += 1;
    } else {
      flags[key] = true;
    }
  }

  return { command, positionals, flags };
}

function stringFlag(flags: Flags, name: string): string | undefined {
  const value = flags[name];
  if (typeof value === "string" && value.trim()) return value.trim();
  return undefined;
}

function numberFlag(flags: Flags, name: string): number | undefined {
  const value = stringFlag(flags, name);
  if (!value) return undefined;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) throw new KanbanStoreError(`--${name} must be a number.`);
  return parsed;
}

function csvFlag(flags: Flags, name: string): string[] {
  return (stringFlag(flags, name) ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function requirePositional(parsed: ParsedArgs, index: number, label: string): string {
  const value = parsed.positionals[index];
  if (!value) throw new KanbanStoreError(`${label} is required.`);
  return value;
}

function quote(value: string): string {
  return JSON.stringify(value);
}

function write(output: string): void {
  process.stdout.write(`${output}\n`);
}

main().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  process.stderr.write(`agent-kanban error: ${message}\n`);
  process.exitCode = error instanceof KanbanStoreError ? Math.min(Math.max(error.statusCode, 1), 255) : 1;
});
