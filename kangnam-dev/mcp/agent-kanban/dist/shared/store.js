import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import path from "node:path";
import { randomUUID } from "node:crypto";
import { createInitialData } from "./initialData.js";
import { resolveProjectDataPath, resolveProjectRoot } from "./projectPaths.js";
import { COLUMN_DEFINITIONS, PRIORITIES, SESSION_OUTCOMES, TEST_STATUSES } from "./types.js";
const DEFAULT_LIMIT = 50;
const MAX_LIMIT = 200;
export class KanbanStoreError extends Error {
    statusCode;
    constructor(message, statusCode = 400) {
        super(message);
        this.statusCode = statusCode;
        this.name = "KanbanStoreError";
    }
}
export function resolveDataPath() {
    return resolveProjectDataPath();
}
export class KanbanStore {
    dataPath;
    defaultCwd;
    constructor(dataPath = resolveDataPath(), defaultCwd = process.cwd()) {
        this.dataPath = dataPath;
        this.defaultCwd = defaultCwd;
    }
    static forCwd(cwd) {
        const projectCwd = cwd?.trim() || process.cwd();
        return new KanbanStore(resolveProjectDataPath(projectCwd), resolveProjectRoot(projectCwd));
    }
    get path() {
        return this.dataPath;
    }
    async load() {
        if (!existsSync(this.dataPath)) {
            const initial = createInitialData(this.defaultCwd);
            await this.save(initial);
            return initial;
        }
        const raw = await readFile(this.dataPath, "utf8");
        const parsed = JSON.parse(raw);
        return normalizeData(parsed);
    }
    async save(data) {
        await mkdir(path.dirname(this.dataPath), { recursive: true });
        const normalized = normalizeData({ ...data, updatedAt: new Date().toISOString() });
        const tempPath = `${this.dataPath}.${process.pid}.${Date.now()}.${randomUUID()}.tmp`;
        await writeFile(tempPath, `${JSON.stringify(normalized, null, 2)}\n`, "utf8");
        await rename(tempPath, this.dataPath);
    }
    async getBoard() {
        return this.load();
    }
    async getMetrics() {
        const data = await this.load();
        return computeMetrics(data.cards);
    }
    async listCards(filters = {}) {
        const data = await this.load();
        const offset = Math.max(0, filters.offset ?? 0);
        const limit = Math.min(Math.max(1, filters.limit ?? DEFAULT_LIMIT), MAX_LIMIT);
        const cards = applyFilters(data.cards, filters).sort(compareCards);
        const page = cards.slice(offset, offset + limit);
        const nextOffset = offset + page.length;
        return {
            total: cards.length,
            count: page.length,
            offset,
            hasMore: nextOffset < cards.length,
            ...(nextOffset < cards.length ? { nextOffset } : {}),
            cards: page
        };
    }
    async getContext(input = {}) {
        const data = await this.load();
        const activeStatuses = new Set(["ready", "in_progress", "review", "blocked"]);
        const scopedCards = data.cards.filter((card) => {
            if (!input.includeDone && card.status === "done")
                return false;
            if (input.branch && card.branch && card.branch !== input.branch)
                return false;
            return true;
        });
        const activeCards = scopedCards
            .filter((card) => {
            if (!activeStatuses.has(card.status))
                return false;
            if (input.agentSessionId && card.assignee.sessionId === input.agentSessionId)
                return true;
            return card.status === "in_progress" || card.status === "review";
        })
            .sort(compareCards)
            .slice(0, input.limit ?? 10);
        const recommendedCards = scopedCards
            .filter((card) => card.status === "ready" && card.assignee.kind !== "user")
            .sort(compareCards)
            .slice(0, input.limit ?? 10);
        const blockedCards = scopedCards.filter((card) => card.status === "blocked").sort(compareCards).slice(0, input.limit ?? 10);
        const reviewCards = scopedCards.filter((card) => card.status === "review").sort(compareCards).slice(0, input.limit ?? 10);
        const metrics = computeMetrics(data.cards);
        const guidance = buildGuidance({ activeCards, recommendedCards, blockedCards, reviewCards, ...(input.agentSessionId ? { agentSessionId: input.agentSessionId } : {}) });
        return {
            ...(input.cwd ? { cwd: input.cwd } : {}),
            ...(input.branch ? { branch: input.branch } : {}),
            ...(input.agentSessionId ? { agentSessionId: input.agentSessionId } : {}),
            activeCards,
            recommendedCards,
            blockedCards,
            reviewCards,
            metrics,
            guidance
        };
    }
    async createCard(input) {
        validateNonEmpty(input.title, "title");
        return this.mutate((data) => {
            const now = new Date().toISOString();
            const card = {
                id: nextCardId(data.cards),
                title: input.title.trim(),
                description: input.description?.trim() ?? "",
                status: input.status ?? "backlog",
                priority: input.priority ?? "medium",
                project: input.project?.trim() || data.settings.defaultProject,
                cwd: this.defaultCwd,
                ...(input.branch?.trim() ? { branch: input.branch.trim() } : {}),
                tags: sanitizeTags(input.tags),
                assignee: { kind: "unassigned" },
                nextAction: input.nextAction?.trim() ?? "",
                filesTouched: [],
                tests: [],
                blockers: [],
                activity: [activity("system", "created", "Card created.")],
                createdAt: now,
                updatedAt: now
            };
            data.cards.push(card);
            return card;
        });
    }
    async claimCard(input) {
        validateNonEmpty(input.cardId, "cardId");
        validateNonEmpty(input.agentSessionId, "agentSessionId");
        return this.mutate((data) => {
            const card = requireCard(data, input.cardId);
            const session = findOrCreateSession(data, {
                agentSessionId: input.agentSessionId,
                cwd: input.cwd ?? card.cwd,
                ...(input.branch ?? card.branch ? { branch: input.branch ?? card.branch } : {})
            });
            card.status = "in_progress";
            card.assignee = { kind: "agent", name: "LLM Agent", sessionId: input.agentSessionId };
            card.cwd = this.defaultCwd;
            if (input.branch)
                card.branch = input.branch;
            card.updatedAt = new Date().toISOString();
            card.activity.push(activity("agent", "claimed", input.note?.trim() || `Claimed by session ${input.agentSessionId}.`));
            session.activeCardId = card.id;
            session.cwd = card.cwd;
            if (card.branch)
                session.branch = card.branch;
            return card;
        });
    }
    async moveCard(input) {
        validateStatus(input.status);
        return this.mutate((data) => {
            const card = requireCard(data, input.cardId);
            const previous = card.status;
            card.status = input.status;
            if (input.status === "done")
                card.completedAt = new Date().toISOString();
            if (input.status !== "done")
                delete card.completedAt;
            card.updatedAt = new Date().toISOString();
            card.activity.push(activity("agent", "moved", input.note?.trim() || `Moved from ${previous} to ${input.status}.`, { from: previous, to: input.status }));
            return card;
        });
    }
    async appendProgress(input) {
        validateNonEmpty(input.message, "message");
        return this.mutate((data) => {
            const card = requireCard(data, input.cardId);
            const touched = input.filesTouched?.map((file) => file.trim()).filter(Boolean) ?? [];
            card.filesTouched = unique([...card.filesTouched, ...touched]);
            if (input.nextAction !== undefined)
                card.nextAction = input.nextAction.trim();
            if (input.test)
                card.tests.push(toTestResult(input.test));
            card.updatedAt = new Date().toISOString();
            card.activity.push(activity("agent", "progress", input.message.trim(), { filesTouched: touched }));
            return card;
        });
    }
    async blockCard(input) {
        validateNonEmpty(input.reason, "reason");
        return this.mutate((data) => {
            const card = requireCard(data, input.cardId);
            card.status = "blocked";
            card.blockers.push({ id: id("blk"), reason: input.reason.trim(), createdAt: new Date().toISOString() });
            if (input.nextAction !== undefined)
                card.nextAction = input.nextAction.trim();
            card.updatedAt = new Date().toISOString();
            card.activity.push(activity("agent", "blocked", input.reason.trim()));
            return card;
        });
    }
    async completeCard(input) {
        validateNonEmpty(input.summary, "summary");
        return this.mutate((data) => {
            const card = requireCard(data, input.cardId);
            card.status = "done";
            card.completedAt = new Date().toISOString();
            card.nextAction = "";
            for (const test of input.tests ?? [])
                card.tests.push(toTestResult(test));
            for (const blocker of card.blockers) {
                if (!blocker.resolvedAt)
                    blocker.resolvedAt = new Date().toISOString();
            }
            card.updatedAt = new Date().toISOString();
            card.activity.push(activity("agent", "completed", input.summary.trim()));
            return card;
        });
    }
    async startSession(input) {
        validateNonEmpty(input.cwd, "cwd");
        const session = await this.mutate((data) => {
            const existing = input.agentSessionId ? data.sessions.find((item) => item.id === input.agentSessionId) : undefined;
            if (existing && !existing.endedAt)
                return existing;
            const created = {
                id: input.agentSessionId?.trim() || id("ses"),
                cwd: input.cwd.trim(),
                ...(input.branch?.trim() ? { branch: input.branch.trim() } : {}),
                ...(input.focus?.trim() ? { focus: input.focus.trim() } : {}),
                startedAt: new Date().toISOString()
            };
            data.sessions.push(created);
            return created;
        });
        const context = await this.getContext({ cwd: session.cwd, branch: session.branch, agentSessionId: session.id });
        return { session, context };
    }
    async endSession(input) {
        validateNonEmpty(input.agentSessionId, "agentSessionId");
        validateOutcome(input.outcome);
        validateNonEmpty(input.summary, "summary");
        return this.mutate((data) => {
            const session = data.sessions.find((item) => item.id === input.agentSessionId);
            if (!session)
                throw new KanbanStoreError(`Session ${input.agentSessionId} was not found. Call kanban_start_session first.`, 404);
            session.endedAt = new Date().toISOString();
            session.outcome = input.outcome;
            session.summary = input.summary.trim();
            if (session.activeCardId) {
                const card = data.cards.find((item) => item.id === session.activeCardId);
                if (card) {
                    if (input.nextAction !== undefined)
                        card.nextAction = input.nextAction.trim();
                    card.activity.push(activity("agent", "session_ended", input.summary.trim(), { outcome: input.outcome, sessionId: session.id }));
                    card.updatedAt = new Date().toISOString();
                }
            }
            return session;
        });
    }
    async mutate(fn) {
        const data = await this.load();
        const result = fn(data);
        await this.save(data);
        return result;
    }
}
function normalizeData(data) {
    return {
        version: 1,
        settings: {
            title: data.settings?.title || "Agent Kanban",
            owner: data.settings?.owner || "Local developer",
            defaultProject: data.settings?.defaultProject || "default",
            columns: COLUMN_DEFINITIONS
        },
        cards: Array.isArray(data.cards) ? data.cards : [],
        sessions: Array.isArray(data.sessions) ? data.sessions : [],
        updatedAt: data.updatedAt || new Date().toISOString()
    };
}
function applyFilters(cards, filters) {
    const query = filters.query?.trim().toLowerCase();
    return cards.filter((card) => {
        if (!filters.includeDone && card.status === "done")
            return false;
        if (filters.status && card.status !== filters.status)
            return false;
        if (filters.project && card.project !== filters.project)
            return false;
        if (filters.cwd && card.cwd !== filters.cwd)
            return false;
        if (filters.branch && card.branch !== filters.branch)
            return false;
        if (filters.tag && !card.tags.includes(filters.tag))
            return false;
        if (filters.assigneeKind && card.assignee.kind !== filters.assigneeKind)
            return false;
        if (query) {
            const haystack = [card.id, card.title, card.description, card.nextAction, card.project, card.cwd, card.branch ?? "", card.tags.join(" ")].join(" ").toLowerCase();
            if (!haystack.includes(query))
                return false;
        }
        return true;
    });
}
function computeMetrics(cards) {
    const byStatus = Object.fromEntries(COLUMN_DEFINITIONS.map((column) => [column.id, 0]));
    for (const card of cards)
        byStatus[card.status] += 1;
    return {
        total: cards.length,
        active: cards.filter((card) => card.status !== "done").length,
        blocked: byStatus.blocked,
        review: byStatus.review,
        done: byStatus.done,
        byStatus
    };
}
function compareCards(a, b) {
    const priority = priorityRank(a.priority) - priorityRank(b.priority);
    if (priority !== 0)
        return priority;
    return Date.parse(b.updatedAt) - Date.parse(a.updatedAt);
}
function priorityRank(priority) {
    return PRIORITIES.indexOf(priority);
}
function buildGuidance(input) {
    const guidance = [];
    if (input.activeCards.length > 0) {
        guidance.push(`Continue active card ${input.activeCards[0]?.id}: ${input.activeCards[0]?.nextAction || input.activeCards[0]?.title}.`);
    }
    else if (input.recommendedCards.length > 0) {
        guidance.push(`Claim recommended card ${input.recommendedCards[0]?.id} before editing files.`);
    }
    else {
        guidance.push("No ready card is available. Create a card before starting new implementation work.");
    }
    if (input.reviewCards.length > 0)
        guidance.push(`${input.reviewCards.length} card(s) are waiting for review or verification.`);
    if (input.blockedCards.length > 0)
        guidance.push(`${input.blockedCards.length} blocked card(s) need user input or a decision.`);
    if (input.agentSessionId)
        guidance.push(`Use agentSessionId ${input.agentSessionId} in claim/progress/end-session calls.`);
    return guidance;
}
function requireCard(data, cardId) {
    const card = data.cards.find((item) => item.id === cardId);
    if (!card)
        throw new KanbanStoreError(`Card ${cardId} was not found. Use kanban_list_cards to find a valid card id.`, 404);
    return card;
}
function findOrCreateSession(data, input) {
    const existing = input.agentSessionId ? data.sessions.find((item) => item.id === input.agentSessionId) : undefined;
    if (existing)
        return existing;
    const created = {
        id: input.agentSessionId?.trim() || id("ses"),
        cwd: input.cwd.trim(),
        ...(input.branch?.trim() ? { branch: input.branch.trim() } : {}),
        ...(input.focus?.trim() ? { focus: input.focus.trim() } : {}),
        startedAt: new Date().toISOString()
    };
    data.sessions.push(created);
    return created;
}
function nextCardId(cards) {
    const max = cards.reduce((acc, card) => {
        const match = /^KBN-(\d+)$/.exec(card.id);
        return match ? Math.max(acc, Number(match[1])) : acc;
    }, 1000);
    return `KBN-${max + 1}`;
}
function activity(actor, type, message, metadata) {
    return {
        id: id("act"),
        at: new Date().toISOString(),
        actor,
        type,
        message,
        ...(metadata ? { metadata } : {})
    };
}
function toTestResult(input) {
    validateNonEmpty(input.command, "test.command");
    validateTestStatus(input.status);
    validateNonEmpty(input.summary, "test.summary");
    return {
        id: id("tst"),
        at: new Date().toISOString(),
        command: input.command.trim(),
        status: input.status,
        summary: input.summary.trim(),
        ...(input.output?.trim() ? { output: input.output.trim() } : {})
    };
}
function validateStatus(status) {
    if (!COLUMN_DEFINITIONS.some((column) => column.id === status)) {
        throw new KanbanStoreError(`Invalid status ${status}. Expected one of: ${COLUMN_DEFINITIONS.map((column) => column.id).join(", ")}.`);
    }
}
function validateOutcome(outcome) {
    if (!SESSION_OUTCOMES.includes(outcome)) {
        throw new KanbanStoreError(`Invalid outcome ${outcome}. Expected one of: ${SESSION_OUTCOMES.join(", ")}.`);
    }
}
function validateTestStatus(status) {
    if (!TEST_STATUSES.includes(status)) {
        throw new KanbanStoreError(`Invalid test status ${status}. Expected one of: ${TEST_STATUSES.join(", ")}.`);
    }
}
function validateNonEmpty(value, field) {
    if (!value || !value.trim())
        throw new KanbanStoreError(`${field} is required.`);
}
function sanitizeTags(tags) {
    return unique((tags ?? []).map((tag) => tag.trim().toLowerCase()).filter(Boolean));
}
function unique(values) {
    return [...new Set(values)];
}
function id(prefix) {
    return `${prefix}_${randomUUID().slice(0, 8)}`;
}
