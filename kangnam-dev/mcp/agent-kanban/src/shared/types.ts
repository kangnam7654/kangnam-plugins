export const COLUMN_DEFINITIONS = [
  { id: "backlog", label: "Backlog", shortLabel: "Backlog", intent: "Captured but not ready" },
  { id: "ready", label: "Ready", shortLabel: "Ready", intent: "Actionable next work" },
  { id: "in_progress", label: "In Progress", shortLabel: "Doing", intent: "Currently owned work" },
  { id: "review", label: "Review", shortLabel: "Review", intent: "Needs user or verification review" },
  { id: "blocked", label: "Blocked", shortLabel: "Blocked", intent: "Needs a decision or missing input" },
  { id: "done", label: "Done", shortLabel: "Done", intent: "Verified and complete" }
] as const;

export const PRIORITIES = ["urgent", "high", "medium", "low"] as const;
export const TEST_STATUSES = ["passed", "failed", "skipped"] as const;
export const SESSION_OUTCOMES = ["continued", "blocked", "completed", "abandoned"] as const;

export type CardStatus = (typeof COLUMN_DEFINITIONS)[number]["id"];
export type Priority = (typeof PRIORITIES)[number];
export type TestStatus = (typeof TEST_STATUSES)[number];
export type SessionOutcome = (typeof SESSION_OUTCOMES)[number];

export interface ActivityEntry {
  id: string;
  at: string;
  actor: "agent" | "user" | "system";
  type:
    | "created"
    | "claimed"
    | "moved"
    | "progress"
    | "blocked"
    | "completed"
    | "session_started"
    | "session_ended";
  message: string;
  metadata?: Record<string, unknown> | undefined;
}

export interface TestResult {
  id: string;
  at: string;
  command: string;
  status: TestStatus;
  summary: string;
  output?: string | undefined;
}

export interface Blocker {
  id: string;
  reason: string;
  createdAt: string;
  resolvedAt?: string | undefined;
}

export interface CardAssignee {
  kind: "unassigned" | "agent" | "user";
  name?: string | undefined;
  sessionId?: string | undefined;
}

export interface KanbanCard {
  id: string;
  title: string;
  description: string;
  status: CardStatus;
  priority: Priority;
  project: string;
  cwd: string;
  branch?: string | undefined;
  tags: string[];
  assignee: CardAssignee;
  nextAction: string;
  filesTouched: string[];
  tests: TestResult[];
  blockers: Blocker[];
  activity: ActivityEntry[];
  createdAt: string;
  updatedAt: string;
  completedAt?: string | undefined;
}

export interface AgentSession {
  id: string;
  cwd: string;
  branch?: string | undefined;
  focus?: string | undefined;
  activeCardId?: string | undefined;
  startedAt: string;
  endedAt?: string | undefined;
  outcome?: SessionOutcome | undefined;
  summary?: string | undefined;
}

export interface BoardSettings {
  title: string;
  owner: string;
  defaultProject: string;
  columns: typeof COLUMN_DEFINITIONS;
}

export interface KanbanData {
  version: 1;
  settings: BoardSettings;
  cards: KanbanCard[];
  sessions: AgentSession[];
  updatedAt: string;
}

export interface CardFilters {
  status?: CardStatus | undefined;
  project?: string | undefined;
  cwd?: string | undefined;
  branch?: string | undefined;
  tag?: string | undefined;
  assigneeKind?: CardAssignee["kind"] | undefined;
  query?: string | undefined;
  includeDone?: boolean | undefined;
  limit?: number | undefined;
  offset?: number | undefined;
}

export interface PaginatedCards {
  total: number;
  count: number;
  offset: number;
  hasMore: boolean;
  nextOffset?: number | undefined;
  cards: KanbanCard[];
}

export interface BoardMetrics {
  total: number;
  active: number;
  blocked: number;
  review: number;
  done: number;
  byStatus: Record<CardStatus, number>;
}

export interface BoardContext {
  cwd?: string | undefined;
  branch?: string | undefined;
  agentSessionId?: string | undefined;
  activeCards: KanbanCard[];
  recommendedCards: KanbanCard[];
  blockedCards: KanbanCard[];
  reviewCards: KanbanCard[];
  metrics: BoardMetrics;
  guidance: string[];
}

export interface CreateCardInput {
  title: string;
  description?: string | undefined;
  status?: CardStatus | undefined;
  priority?: Priority | undefined;
  project?: string | undefined;
  cwd?: string | undefined;
  branch?: string | undefined;
  tags?: string[] | undefined;
  nextAction?: string | undefined;
}

export interface ClaimCardInput {
  cardId: string;
  agentSessionId: string;
  cwd?: string | undefined;
  branch?: string | undefined;
  note?: string | undefined;
}

export interface MoveCardInput {
  cardId: string;
  cwd?: string | undefined;
  status: CardStatus;
  note?: string | undefined;
}

export interface AppendProgressInput {
  cardId: string;
  cwd?: string | undefined;
  message: string;
  filesTouched?: string[] | undefined;
  nextAction?: string | undefined;
  test?: Omit<TestResult, "id" | "at"> | undefined;
}

export interface BlockCardInput {
  cardId: string;
  cwd?: string | undefined;
  reason: string;
  nextAction?: string | undefined;
}

export interface CompleteCardInput {
  cardId: string;
  cwd?: string | undefined;
  summary: string;
  tests?: Omit<TestResult, "id" | "at">[] | undefined;
}

export interface StartSessionInput {
  agentSessionId?: string | undefined;
  cwd: string;
  branch?: string | undefined;
  focus?: string | undefined;
}

export interface EndSessionInput {
  agentSessionId: string;
  cwd?: string | undefined;
  outcome: SessionOutcome;
  summary: string;
  nextAction?: string | undefined;
}
