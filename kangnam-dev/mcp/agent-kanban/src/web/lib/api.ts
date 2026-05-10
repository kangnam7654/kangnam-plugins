import type {
  AgentSession,
  AppendProgressInput,
  BoardMetrics,
  CardStatus,
  CreateCardInput,
  KanbanCard,
  KanbanData,
  Priority,
  StartSessionInput
} from "../../shared/types.js";

export interface BoardResponse {
  board: KanbanData;
  metrics: BoardMetrics;
}

export interface SessionResponse {
  session: AgentSession;
}

export async function fetchBoard(cwd?: string): Promise<BoardResponse> {
  return request<BoardResponse>(`/api/board${cwd ? `?cwd=${encodeURIComponent(cwd)}` : ""}`);
}

export async function createCard(input: CreateCardInput): Promise<KanbanCard> {
  return request<KanbanCard>("/api/cards", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function moveCard(cardId: string, status: CardStatus, note?: string, cwd?: string): Promise<KanbanCard> {
  return request<KanbanCard>(`/api/cards/${cardId}/move`, {
    method: "POST",
    body: JSON.stringify({ status, note, cwd })
  });
}

export async function claimCard(cardId: string, agentSessionId: string, cwd?: string, branch?: string): Promise<KanbanCard> {
  return request<KanbanCard>(`/api/cards/${cardId}/claim`, {
    method: "POST",
    body: JSON.stringify({ agentSessionId, cwd, branch, note: "Claimed from the web board." })
  });
}

export async function appendProgress(input: AppendProgressInput): Promise<KanbanCard> {
  return request<KanbanCard>(`/api/cards/${input.cardId}/progress`, {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export async function blockCard(cardId: string, reason: string, nextAction: string, cwd?: string): Promise<KanbanCard> {
  return request<KanbanCard>(`/api/cards/${cardId}/block`, {
    method: "POST",
    body: JSON.stringify({ reason, nextAction, cwd })
  });
}

export async function completeCard(cardId: string, summary: string, cwd?: string): Promise<KanbanCard> {
  return request<KanbanCard>(`/api/cards/${cardId}/complete`, {
    method: "POST",
    body: JSON.stringify({ summary, tests: [], cwd })
  });
}

export async function startSession(input: StartSessionInput): Promise<SessionResponse> {
  return request<SessionResponse>("/api/sessions/start", {
    method: "POST",
    body: JSON.stringify(input)
  });
}

export function priorityLabel(priority: Priority): string {
  return priority.charAt(0).toUpperCase() + priority.slice(1);
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => ({ error: response.statusText }))) as { error?: string };
    throw new Error(body.error || response.statusText);
  }
  return (await response.json()) as T;
}
