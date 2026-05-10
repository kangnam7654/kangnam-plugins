import {
  Activity,
  ArrowRight,
  BadgeCheck,
  Ban,
  Blocks,
  Check,
  ClipboardList,
  FileCode2,
  GitBranch,
  GripVertical,
  ListFilter,
  Loader2,
  MessageSquarePlus,
  Plus,
  RefreshCw,
  Search,
  ShieldAlert,
  Sparkles,
  TerminalSquare,
  UserRound
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { COLUMN_DEFINITIONS } from "../shared/types.js";
import type { ActivityEntry, BoardMetrics, CardStatus, KanbanCard, Priority, TestStatus } from "../shared/types.js";
import {
  appendProgress,
  blockCard,
  claimCard,
  completeCard,
  createCard,
  fetchBoard,
  moveCard,
  priorityLabel,
  startSession
} from "./lib/api.js";

const statusOrder = COLUMN_DEFINITIONS.map((column) => column.id);

export function App() {
  const [cards, setCards] = useState<KanbanCard[]>([]);
  const [metrics, setMetrics] = useState<BoardMetrics | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [hideDone, setHideDone] = useState(false);
  const [draggedId, setDraggedId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState("");
  const [sessionCwd, setSessionCwd] = useState("");
  const [sessionBranch, setSessionBranch] = useState("");

  const selected = useMemo(() => cards.find((card) => card.id === selectedId) ?? cards[0] ?? null, [cards, selectedId]);
  const visibleCards = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return cards.filter((card) => {
      if (hideDone && card.status === "done") return false;
      if (!normalized) return true;
      const haystack = [card.id, card.title, card.description, card.project, card.cwd, card.branch ?? "", card.nextAction, card.tags.join(" ")].join(" ").toLowerCase();
      return haystack.includes(normalized);
    });
  }, [cards, hideDone, query]);

  useEffect(() => {
    void refresh();
  }, []);

  async function refresh(cwd = sessionCwd) {
    setBusy(true);
    setError(null);
    try {
      const response = await fetchBoard(cwd || undefined);
      setCards(response.board.cards);
      setMetrics(response.metrics);
      const defaultCwd = response.board.cards[0]?.cwd ?? "";
      setSessionCwd((current) => current || defaultCwd);
      setSelectedId((current) => current ?? response.board.cards[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load board.");
    } finally {
      setBusy(false);
    }
  }

  async function run(action: () => Promise<KanbanCard | unknown>) {
    setBusy(true);
    setError(null);
    try {
      await action();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  async function handleDrop(status: CardStatus) {
    if (!draggedId) return;
      const card = cards.find((item) => item.id === draggedId);
      await run(() => moveCard(draggedId, status, `Moved to ${status} from the board.`, card?.cwd));
    setDraggedId(null);
  }

  async function handleStartSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await run(async () => {
      const response = await startSession({
        cwd: sessionCwd,
        ...(sessionId.trim() ? { agentSessionId: sessionId.trim() } : {}),
        ...(sessionBranch.trim() ? { branch: sessionBranch.trim() } : {})
      });
      setSessionId(response.session.id);
      await refresh(sessionCwd);
      return response;
    });
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark">
            <Blocks size={20} />
          </div>
          <div>
            <h1>Agent Kanban</h1>
            <p>Local development board</p>
          </div>
        </div>

        <section className="metric-grid" aria-label="Board metrics">
          <Metric label="Active" value={metrics?.active ?? 0} />
          <Metric label="Blocked" value={metrics?.blocked ?? 0} tone="danger" />
          <Metric label="Review" value={metrics?.review ?? 0} tone="amber" />
          <Metric label="Done" value={metrics?.done ?? 0} tone="green" />
        </section>

        <form className="session-panel" onSubmit={handleStartSession}>
          <div className="section-title">
            <TerminalSquare size={16} />
            <span>Session</span>
          </div>
          <label>
            <span>CWD</span>
            <input value={sessionCwd} onChange={(event) => setSessionCwd(event.target.value)} placeholder="/project/path" required />
          </label>
          <label>
            <span>Branch</span>
            <input value={sessionBranch} onChange={(event) => setSessionBranch(event.target.value)} placeholder="optional" />
          </label>
          <label>
            <span>Session ID</span>
            <input value={sessionId} onChange={(event) => setSessionId(event.target.value)} placeholder="auto" />
          </label>
          <button type="submit" className="primary-action" disabled={busy}>
            <Sparkles size={16} />
            Start
          </button>
        </form>

        <CreateCardForm onCreate={(input) => run(() => createCard(input))} defaultCwd={sessionCwd} />
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="search-box">
            <Search size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search cards, files, tags" />
          </div>
          <button type="button" className={hideDone ? "toggle active" : "toggle"} onClick={() => setHideDone((value) => !value)}>
            <ListFilter size={16} />
            Active only
          </button>
          <button type="button" className="icon-button" onClick={() => void refresh()} disabled={busy} aria-label="Refresh board" title="Refresh board">
            {busy ? <Loader2 size={17} className="spin" /> : <RefreshCw size={17} />}
          </button>
        </header>

        {error ? <div className="error-strip">{error}</div> : null}

        <div className="board" aria-label="Kanban board">
          {COLUMN_DEFINITIONS.map((column) => {
            const columnCards = visibleCards.filter((card) => card.status === column.id);
            return (
              <section
                key={column.id}
                className={`column column-${column.id}`}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => void handleDrop(column.id)}
              >
                <header className="column-header">
                  <div>
                    <h2>{column.label}</h2>
                    <p>{column.intent}</p>
                  </div>
                  <span>{columnCards.length}</span>
                </header>
                <div className="card-stack">
                  {columnCards.map((card) => (
                    <KanbanCardView
                      key={card.id}
                      card={card}
                      selected={card.id === selected?.id}
                      onSelect={() => setSelectedId(card.id)}
                      onDragStart={() => setDraggedId(card.id)}
                      onClaim={() => run(() => claimCard(card.id, sessionId || `web_${Date.now()}`, card.cwd, card.branch))}
                      onNext={() => run(() => moveCard(card.id, nextStatus(card.status), `Advanced to ${nextStatus(card.status)}.`, card.cwd))}
                    />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      </section>

      <CardDetailPanel
        card={selected}
        onMove={(status) => selected && run(() => moveCard(selected.id, status, `Moved to ${status} from detail panel.`, selected.cwd))}
        onBlock={(reason, nextAction) => selected && run(() => blockCard(selected.id, reason, nextAction, selected.cwd))}
        onComplete={(summary) => selected && run(() => completeCard(selected.id, summary, selected.cwd))}
        onProgress={(input) => run(() => appendProgress(input))}
      />
    </main>
  );
}

function Metric({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "danger" | "amber" | "green" }) {
  return (
    <div className={`metric metric-${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function CreateCardForm({ onCreate, defaultCwd }: { onCreate: (input: { title: string; priority: Priority; status: CardStatus; cwd?: string; tags: string[]; nextAction?: string }) => void; defaultCwd: string }) {
  const [title, setTitle] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [status, setStatus] = useState<CardStatus>("backlog");
  const [tags, setTags] = useState("");
  const [nextAction, setNextAction] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate({
      title,
      priority,
      status,
      ...(defaultCwd ? { cwd: defaultCwd } : {}),
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      ...(nextAction.trim() ? { nextAction: nextAction.trim() } : {})
    });
    setTitle("");
    setTags("");
    setNextAction("");
  }

  return (
    <form className="create-panel" onSubmit={submit}>
      <div className="section-title">
        <Plus size={16} />
        <span>New card</span>
      </div>
      <label>
        <span>Title</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Work item" required />
      </label>
      <div className="field-row">
        <label>
          <span>Status</span>
          <select value={status} onChange={(event) => setStatus(event.target.value as CardStatus)}>
            {COLUMN_DEFINITIONS.map((column) => (
              <option key={column.id} value={column.id}>
                {column.shortLabel}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Priority</span>
          <select value={priority} onChange={(event) => setPriority(event.target.value as Priority)}>
            {(["urgent", "high", "medium", "low"] as const).map((item) => (
              <option key={item} value={item}>
                {priorityLabel(item)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        <span>Tags</span>
        <input value={tags} onChange={(event) => setTags(event.target.value)} placeholder="api, ui" />
      </label>
      <label>
        <span>Next action</span>
        <textarea value={nextAction} onChange={(event) => setNextAction(event.target.value)} rows={3} />
      </label>
      <button type="submit" className="primary-action">
        <MessageSquarePlus size={16} />
        Add card
      </button>
    </form>
  );
}

function KanbanCardView({
  card,
  selected,
  onSelect,
  onDragStart,
  onClaim,
  onNext
}: {
  card: KanbanCard;
  selected: boolean;
  onSelect: () => void;
  onDragStart: () => void;
  onClaim: () => void;
  onNext: () => void;
}) {
  const latestTest = card.tests.at(-1);
  const openBlockers = card.blockers.filter((blocker) => !blocker.resolvedAt).length;

  return (
    <article className={selected ? "work-card selected" : "work-card"} draggable onDragStart={onDragStart} onClick={onSelect}>
      <div className="card-topline">
        <span className="card-id">{card.id}</span>
        <PriorityPill priority={card.priority} />
        <GripVertical size={15} className="drag-handle" />
      </div>
      <h3>{card.title}</h3>
      {card.nextAction ? <p className="next-action">{card.nextAction}</p> : null}
      <div className="tag-row">
        {card.tags.slice(0, 3).map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>
      <div className="card-meta-grid">
        <Meta icon={<UserRound size={14} />} text={card.assignee.sessionId ?? card.assignee.name ?? card.assignee.kind} />
        <Meta icon={<GitBranch size={14} />} text={card.branch ?? "no branch"} />
        <Meta icon={<FileCode2 size={14} />} text={`${card.filesTouched.length} files`} />
        <Meta icon={<Activity size={14} />} text={`${card.activity.length} logs`} />
      </div>
      <div className="card-footer">
        <span className={latestTest ? `test-chip test-${latestTest.status}` : "test-chip"}>{latestTest ? latestTest.status : "no tests"}</span>
        {openBlockers > 0 ? <span className="blocker-chip">{openBlockers} blocked</span> : null}
        <button type="button" onClick={(event) => { event.stopPropagation(); onClaim(); }} title="Claim card" aria-label="Claim card">
          <Check size={14} />
        </button>
        {card.status !== "done" ? (
          <button type="button" onClick={(event) => { event.stopPropagation(); onNext(); }} title="Move next" aria-label="Move next">
            <ArrowRight size={14} />
          </button>
        ) : null}
      </div>
    </article>
  );
}

function CardDetailPanel({
  card,
  onMove,
  onBlock,
  onComplete,
  onProgress
}: {
  card: KanbanCard | null;
  onMove: (status: CardStatus) => void;
  onBlock: (reason: string, nextAction: string) => void;
  onComplete: (summary: string) => void;
  onProgress: (input: { cardId: string; cwd?: string; message: string; filesTouched: string[]; nextAction?: string; test?: { command: string; status: TestStatus; summary: string } }) => void;
}) {
  const [message, setMessage] = useState("");
  const [files, setFiles] = useState("");
  const [nextAction, setNextAction] = useState("");
  const [testCommand, setTestCommand] = useState("");
  const [testSummary, setTestSummary] = useState("");
  const [testStatus, setTestStatus] = useState<TestStatus>("passed");
  const [blockReason, setBlockReason] = useState("");
  const [completeSummary, setCompleteSummary] = useState("");

  useEffect(() => {
    setNextAction(card?.nextAction ?? "");
    setMessage("");
    setFiles("");
    setTestCommand("");
    setTestSummary("");
    setBlockReason("");
    setCompleteSummary("");
  }, [card?.id]);

  if (!card) {
    return (
      <aside className="detail-panel empty">
        <ClipboardList size={28} />
        <p>No card selected</p>
      </aside>
    );
  }

  function submitProgress(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!card) return;
    onProgress({
      cardId: card.id,
      cwd: card.cwd,
      message,
      filesTouched: files.split(",").map((file) => file.trim()).filter(Boolean),
      ...(nextAction.trim() ? { nextAction: nextAction.trim() } : {}),
      ...(testCommand.trim() && testSummary.trim()
        ? {
            test: {
              command: testCommand.trim(),
              status: testStatus,
              summary: testSummary.trim()
            }
          }
        : {})
    });
    setMessage("");
    setFiles("");
    setTestCommand("");
    setTestSummary("");
  }

  return (
    <aside className="detail-panel">
      <div className="detail-heading">
        <span>{card.id}</span>
        <PriorityPill priority={card.priority} />
      </div>
      <h2>{card.title}</h2>
      <p className="description">{card.description || "No description"}</p>

      <div className="status-actions">
        {COLUMN_DEFINITIONS.map((column) => (
          <button key={column.id} type="button" className={card.status === column.id ? "active" : ""} onClick={() => onMove(column.id)}>
            {column.shortLabel}
          </button>
        ))}
      </div>

      <section className="detail-section">
        <h3>Work state</h3>
        <dl>
          <div>
            <dt>Project</dt>
            <dd>{card.project}</dd>
          </div>
          <div>
            <dt>CWD</dt>
            <dd>{card.cwd}</dd>
          </div>
          <div>
            <dt>Next</dt>
            <dd>{card.nextAction || "None"}</dd>
          </div>
        </dl>
      </section>

      <form className="progress-form" onSubmit={submitProgress}>
        <h3>Progress</h3>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Progress note" rows={3} required />
        <input value={files} onChange={(event) => setFiles(event.target.value)} placeholder="files, comma-separated" />
        <textarea value={nextAction} onChange={(event) => setNextAction(event.target.value)} placeholder="Next action" rows={2} />
        <div className="field-row">
          <input value={testCommand} onChange={(event) => setTestCommand(event.target.value)} placeholder="test command" />
          <select value={testStatus} onChange={(event) => setTestStatus(event.target.value as TestStatus)}>
            <option value="passed">passed</option>
            <option value="failed">failed</option>
            <option value="skipped">skipped</option>
          </select>
        </div>
        <input value={testSummary} onChange={(event) => setTestSummary(event.target.value)} placeholder="test summary" />
        <button type="submit" className="primary-action">
          <Activity size={16} />
          Save progress
        </button>
      </form>

      <div className="terminal-actions">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onBlock(blockReason, nextAction);
            setBlockReason("");
          }}
        >
          <input value={blockReason} onChange={(event) => setBlockReason(event.target.value)} placeholder="Blocker reason" required />
          <button type="submit">
            <Ban size={15} />
            Block
          </button>
        </form>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            onComplete(completeSummary);
            setCompleteSummary("");
          }}
        >
          <input value={completeSummary} onChange={(event) => setCompleteSummary(event.target.value)} placeholder="Completion summary" required />
          <button type="submit">
            <BadgeCheck size={15} />
            Done
          </button>
        </form>
      </div>

      <section className="detail-section">
        <h3>Activity</h3>
        <ol className="activity-list">
          {card.activity.slice().reverse().slice(0, 8).map((entry) => (
            <ActivityItem key={entry.id} entry={entry} />
          ))}
        </ol>
      </section>
    </aside>
  );
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  return (
    <li>
      <span>{entry.type.replace("_", " ")}</span>
      <p>{entry.message}</p>
      <time>{new Date(entry.at).toLocaleString()}</time>
    </li>
  );
}

function PriorityPill({ priority }: { priority: Priority }) {
  return <span className={`priority priority-${priority}`}>{priority}</span>;
}

function Meta({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <span className="meta-item">
      {icon}
      {text}
    </span>
  );
}

function nextStatus(status: CardStatus): CardStatus {
  const index = statusOrder.indexOf(status);
  return statusOrder[Math.min(index + 1, statusOrder.length - 1)] ?? "done";
}
