import {
  Activity,
  BadgeCheck,
  Ban,
  Blocks,
  CheckCircle2,
  ClipboardList,
  FileCode2,
  GitBranch,
  Layers3,
  ListFilter,
  Loader2,
  MessageSquarePlus,
  MoveRight,
  Plus,
  RefreshCw,
  Search,
  TerminalSquare,
  UserRound
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { COLUMN_DEFINITIONS } from "../shared/types.js";
import type { ActivityEntry, BoardMetrics, CardKind, CardStatus, CreateCardInput, KanbanCard, Priority, TestStatus } from "../shared/types.js";
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
const initialCwd = new URLSearchParams(window.location.search).get("cwd") ?? "";

interface EpicGroup {
  id: string;
  title: string;
  description: string;
  epic?: KanbanCard | undefined;
  cards: KanbanCard[];
}

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
  const [sessionCwd, setSessionCwd] = useState(initialCwd);
  const [sessionBranch, setSessionBranch] = useState("");

  const epicOptions = useMemo(() => cards.filter((card) => card.kind === "epic").sort(compareByUpdated), [cards]);
  const epicLookup = useMemo(() => new Map(epicOptions.map((epic) => [epic.id, epic])), [epicOptions]);

  const visibleCards = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return cards.filter((card) => {
      if (hideDone && card.status === "done") return false;
      if (!normalized) return true;
      const epicTitle = card.epicId ? epicLookup.get(card.epicId)?.title ?? "" : "";
      const haystack = [card.id, card.title, card.description, card.kind, epicTitle, card.project, card.cwd, card.branch ?? "", card.nextAction, card.tags.join(" ")]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalized);
    });
  }, [cards, epicLookup, hideDone, query]);

  const selected = useMemo(() => cards.find((card) => card.id === selectedId) ?? visibleCards[0] ?? cards[0] ?? null, [cards, selectedId, visibleCards]);
  const selectedChildren = useMemo(() => (selected?.kind === "epic" ? cards.filter((card) => card.epicId === selected.id) : []), [cards, selected]);
  const boardGroups = useMemo(() => buildEpicGroups(cards, visibleCards), [cards, visibleCards]);

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
      setSelectedId((current) => {
        if (current && response.board.cards.some((card) => card.id === current)) return current;
        return response.board.cards[0]?.id ?? null;
      });
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
            <p>Epic swimlanes for agent work</p>
          </div>
        </div>

        <section className="metric-grid" aria-label="Board metrics">
          <Metric label="Epics" value={metrics?.epics ?? 0} />
          <Metric label="Tasks" value={metrics?.tasks ?? 0} />
          <Metric label="Blocked" value={metrics?.blocked ?? 0} tone="danger" />
          <Metric label="Review" value={metrics?.review ?? 0} tone="amber" />
        </section>

        <form className="session-panel" onSubmit={handleStartSession}>
          <div className="section-title">
            <TerminalSquare size={16} />
            <span>Session</span>
          </div>
          <label>
            <span>Project path</span>
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
            <CheckCircle2 size={16} />
            Start session
          </button>
        </form>

        <CreateCardForm onCreate={(input) => run(() => createCard(input))} defaultCwd={sessionCwd} epics={epicOptions} />
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div className="search-box">
            <Search size={17} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search epics, cards, files, tags" />
          </div>
          <button type="button" className={hideDone ? "toggle active" : "toggle"} onClick={() => setHideDone((value) => !value)}>
            <ListFilter size={16} />
            Active only
          </button>
          <button type="button" className="secondary-action" onClick={() => void refresh()} disabled={busy}>
            {busy ? <Loader2 size={17} className="spin" /> : <RefreshCw size={17} />}
            Refresh
          </button>
        </header>

        {error ? <div className="error-strip">{error}</div> : null}

        <div className="board" aria-label="Kanban board grouped by epic">
          {boardGroups.length > 0 ? (
            boardGroups.map((group) => (
              <EpicSwimlane
                key={group.id}
                group={group}
                selectedId={selected?.id ?? null}
                draggedId={draggedId}
                onDrop={handleDrop}
                onSelect={setSelectedId}
                onDragStart={setDraggedId}
                onClaim={(card) => run(() => claimCard(card.id, sessionId || `web_${Date.now()}`, card.cwd, card.branch))}
                onNext={(card) => run(() => moveCard(card.id, nextStatus(card.status), `Advanced to ${nextStatus(card.status)}.`, card.cwd))}
              />
            ))
          ) : (
            <div className="empty-board">
              <Layers3 size={28} />
              <strong>No cards yet</strong>
              <span>Create an epic first, then add Ready tasks under it.</span>
            </div>
          )}
        </div>
      </section>

      <CardDetailPanel
        card={selected}
        children={selectedChildren}
        epic={selected?.epicId ? epicLookup.get(selected.epicId) : undefined}
        onMove={(status) => selected && run(() => moveCard(selected.id, status, `Moved to ${status} from detail panel.`, selected.cwd))}
        onBlock={(reason, nextAction) => selected && run(() => blockCard(selected.id, reason, nextAction, selected.cwd))}
        onComplete={(summary) => selected && run(() => completeCard(selected.id, summary, selected.cwd))}
        onProgress={(input) => run(() => appendProgress(input))}
      />
    </main>
  );
}

function Metric({ label, value, tone = "default" }: { label: string; value: number; tone?: "default" | "danger" | "amber" }) {
  return (
    <div className={`metric metric-${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function CreateCardForm({ onCreate, defaultCwd, epics }: { onCreate: (input: CreateCardInput) => void; defaultCwd: string; epics: KanbanCard[] }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [kind, setKind] = useState<CardKind>("task");
  const [epicId, setEpicId] = useState("");
  const [priority, setPriority] = useState<Priority>("medium");
  const [status, setStatus] = useState<CardStatus>("ready");
  const [tags, setTags] = useState("");
  const [nextAction, setNextAction] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onCreate({
      title,
      kind,
      priority,
      status,
      ...(defaultCwd ? { cwd: defaultCwd } : {}),
      ...(description.trim() ? { description: description.trim() } : {}),
      ...(kind === "task" && epicId ? { epicId } : {}),
      tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      ...(nextAction.trim() ? { nextAction: nextAction.trim() } : {})
    });
    setTitle("");
    setDescription("");
    setTags("");
    setNextAction("");
    if (kind === "task") setStatus("ready");
  }

  return (
    <form className="create-panel" onSubmit={submit}>
      <div className="section-title">
        <Plus size={16} />
        <span>New work item</span>
      </div>
      <label>
        <span>Type</span>
        <select value={kind} onChange={(event) => setKind(event.target.value as CardKind)}>
          <option value="task">Task</option>
          <option value="epic">Epic</option>
        </select>
      </label>
      <label>
        <span>Title</span>
        <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder={kind === "epic" ? "Epic name" : "Task title"} required />
      </label>
      {kind === "task" ? (
        <label>
          <span>Epic</span>
          <select value={epicId} onChange={(event) => setEpicId(event.target.value)}>
            <option value="">No Epic</option>
            {epics.map((epic) => (
              <option key={epic.id} value={epic.id}>
                {epic.id} · {epic.title}
              </option>
            ))}
          </select>
        </label>
      ) : null}
      <label>
        <span>Description Markdown</span>
        <textarea value={description} onChange={(event) => setDescription(event.target.value)} placeholder="- acceptance criteria&#10;- notes" rows={4} />
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
        <textarea value={nextAction} onChange={(event) => setNextAction(event.target.value)} rows={2} />
      </label>
      <button type="submit" className="primary-action">
        <MessageSquarePlus size={16} />
        Add {kind}
      </button>
    </form>
  );
}

function EpicSwimlane({
  group,
  selectedId,
  onDrop,
  onSelect,
  onDragStart,
  onClaim,
  onNext
}: {
  group: EpicGroup;
  selectedId: string | null;
  draggedId: string | null;
  onDrop: (status: CardStatus) => Promise<void>;
  onSelect: (id: string) => void;
  onDragStart: (id: string) => void;
  onClaim: (card: KanbanCard) => void;
  onNext: (card: KanbanCard) => void;
}) {
  const done = group.cards.filter((card) => card.status === "done").length;
  const total = group.cards.length;

  return (
    <section className="epic-lane">
      <button type="button" className="epic-heading" onClick={() => group.epic && onSelect(group.epic.id)}>
        <div>
          <span className="eyebrow">{group.epic ? `${group.epic.id} · Epic` : "No Epic"}</span>
          <h2>{group.title}</h2>
          <p>{group.description}</p>
        </div>
        <div className="epic-progress" aria-label={`${done} of ${total} done`}>
          <strong>{done}/{total}</strong>
          <span>done</span>
        </div>
      </button>

      <div className="swimlane-grid">
        {COLUMN_DEFINITIONS.map((column) => {
          const columnCards = group.cards.filter((card) => card.status === column.id);
          return (
            <section
              key={column.id}
              className={`column column-${column.id}`}
              onDragOver={(event) => event.preventDefault()}
              onDrop={() => void onDrop(column.id)}
            >
              <header className="column-header">
                <div>
                  <h3>{column.label}</h3>
                  <p>{column.intent}</p>
                </div>
                <span>{columnCards.length}</span>
              </header>
              <div className="card-stack">
                {columnCards.map((card) => (
                  <KanbanCardView
                    key={card.id}
                    card={card}
                    selected={card.id === selectedId}
                    onSelect={() => onSelect(card.id)}
                    onDragStart={() => onDragStart(card.id)}
                    onClaim={() => onClaim(card)}
                    onNext={() => onNext(card)}
                  />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </section>
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
  const next = nextStatus(card.status);

  return (
    <article className={selected ? "work-card selected" : "work-card"} draggable onDragStart={onDragStart} onClick={onSelect}>
      <div className="card-topline">
        <span className="card-id">{card.id}</span>
        <PriorityPill priority={card.priority} />
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
      <div className="card-state-row">
        <span className={latestTest ? `test-chip test-${latestTest.status}` : "test-chip"}>{latestTest ? latestTest.status : "no tests"}</span>
        {openBlockers > 0 ? <span className="blocker-chip">{openBlockers} blocked</span> : null}
      </div>
      <div className="card-actions">
        <button type="button" onClick={(event) => { event.stopPropagation(); onClaim(); }}>
          <CheckCircle2 size={14} />
          Claim
        </button>
        {card.status !== "done" ? (
          <button type="button" onClick={(event) => { event.stopPropagation(); onNext(); }}>
            <MoveRight size={14} />
            Move to {columnLabel(next)}
          </button>
        ) : null}
      </div>
    </article>
  );
}

function CardDetailPanel({
  card,
  children,
  epic,
  onMove,
  onBlock,
  onComplete,
  onProgress
}: {
  card: KanbanCard | null;
  children: KanbanCard[];
  epic?: KanbanCard | undefined;
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
        <div>
          <span>{card.id}</span>
          <KindPill kind={card.kind} />
        </div>
        <PriorityPill priority={card.priority} />
      </div>
      <h2>{card.title}</h2>

      {card.kind === "task" && epic ? (
        <div className="parent-epic">
          <Layers3 size={15} />
          <span>{epic.id}</span>
          <strong>{epic.title}</strong>
        </div>
      ) : null}

      <section className="detail-section">
        <h3>Description</h3>
        <MarkdownView source={card.description} empty="No description" />
      </section>

      {card.kind === "epic" ? (
        <section className="detail-section">
          <h3>Epic progress</h3>
          <div className="child-status-grid">
            {COLUMN_DEFINITIONS.map((column) => (
              <div key={column.id}>
                <strong>{children.filter((child) => child.status === column.id).length}</strong>
                <span>{column.shortLabel}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="detail-section">
        <h3>Move status</h3>
        <div className="status-actions">
          {COLUMN_DEFINITIONS.map((column) => (
            <button key={column.id} type="button" className={card.status === column.id ? "active" : ""} onClick={() => onMove(column.id)}>
              {card.status === column.id ? "Currently" : "Move to"} {column.shortLabel}
            </button>
          ))}
        </div>
      </section>

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
            <dt>Next action</dt>
            <dd>{card.nextAction || "None"}</dd>
          </div>
        </dl>
      </section>

      <form className="progress-form" onSubmit={submitProgress}>
        <h3>Record progress</h3>
        <textarea value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Progress note, Markdown allowed" rows={3} required />
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
            Mark blocked
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
            Mark done
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

function MarkdownView({ source, empty }: { source: string; empty?: string }) {
  const blocks = parseMarkdown(source);
  if (blocks.length === 0) return <p className="muted-text">{empty ?? "Empty"}</p>;
  return (
    <div className="markdown-view">
      {blocks.map((block, index) => {
        if (block.type === "heading") return <h4 key={index}>{renderInline(block.text)}</h4>;
        if (block.type === "code") return <pre key={index}><code>{block.text}</code></pre>;
        if (block.type === "ul") {
          return (
            <ul key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  {item.checked !== undefined ? <input type="checkbox" checked={item.checked} readOnly /> : null}
                  <span>{renderInline(item.text)}</span>
                </li>
              ))}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={index}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{renderInline(item.text)}</li>
              ))}
            </ol>
          );
        }
        return <p key={index}>{renderInline(block.text)}</p>;
      })}
    </div>
  );
}

type MarkdownBlock =
  | { type: "heading" | "paragraph" | "code"; text: string }
  | { type: "ul"; items: { text: string; checked?: boolean | undefined }[] }
  | { type: "ol"; items: { text: string }[] };

function parseMarkdown(source: string): MarkdownBlock[] {
  const lines = source.replace(/\\n/g, "\n").trim().split(/\r?\n/);
  const blocks: MarkdownBlock[] = [];
  let paragraph: string[] = [];
  let code: string[] | null = null;

  function flushParagraph() {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  }

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (code) {
        blocks.push({ type: "code", text: code.join("\n") });
        code = null;
      } else {
        flushParagraph();
        code = [];
      }
      continue;
    }
    if (code) {
      code.push(line);
      continue;
    }
    if (!line.trim()) {
      flushParagraph();
      continue;
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "heading", text: heading[2] ?? "" });
      continue;
    }
    const unordered = /^[-*]\s+(\[[ xX]\]\s+)?(.+)$/.exec(line);
    if (unordered) {
      flushParagraph();
      const last = blocks.at(-1);
      const marker = unordered[1];
      const item = { text: unordered[2] ?? "", ...(marker ? { checked: marker.toLowerCase().includes("x") } : {}) };
      if (last?.type === "ul") last.items.push(item);
      else blocks.push({ type: "ul", items: [item] });
      continue;
    }
    const ordered = /^\d+\.\s+(.+)$/.exec(line);
    if (ordered) {
      flushParagraph();
      const last = blocks.at(-1);
      const item = { text: ordered[1] ?? "" };
      if (last?.type === "ol") last.items.push(item);
      else blocks.push({ type: "ol", items: [item] });
      continue;
    }
    paragraph.push(line.trim());
  }
  flushParagraph();
  if (code) blocks.push({ type: "code", text: code.join("\n") });
  return blocks;
}

function renderInline(text: string): ReactNode[] {
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g;
  const nodes: ReactNode[] = [];
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const start = match.index ?? 0;
    if (start > cursor) nodes.push(text.slice(cursor, start));
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(<code key={`${start}-code`}>{token.slice(1, -1)}</code>);
    } else if (token.startsWith("**")) {
      nodes.push(<strong key={`${start}-strong`}>{token.slice(2, -2)}</strong>);
    } else {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      const href = link?.[2] ?? "";
      if (/^https?:\/\//.test(href)) {
        nodes.push(
          <a key={`${start}-link`} href={href} target="_blank" rel="noreferrer">
            {link?.[1] ?? href}
          </a>
        );
      } else {
        nodes.push(link?.[1] ?? token);
      }
    }
    cursor = start + token.length;
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

function ActivityItem({ entry }: { entry: ActivityEntry }) {
  return (
    <li>
      <span>{entry.type.replace("_", " ")}</span>
      <MarkdownView source={entry.message} />
      <time>{new Date(entry.at).toLocaleString()}</time>
    </li>
  );
}

function PriorityPill({ priority }: { priority: Priority }) {
  return <span className={`priority priority-${priority}`}>{priority}</span>;
}

function KindPill({ kind }: { kind: CardKind }) {
  return <span className={`kind-pill kind-${kind}`}>{kind}</span>;
}

function Meta({ icon, text }: { icon: ReactNode; text: string }) {
  return (
    <span className="meta-item">
      {icon}
      {text}
    </span>
  );
}

function buildEpicGroups(cards: KanbanCard[], visibleCards: KanbanCard[]): EpicGroup[] {
  const visibleIds = new Set(visibleCards.map((card) => card.id));
  const epics = cards.filter((card) => card.kind === "epic").sort(compareByUpdated);
  const tasks = visibleCards.filter((card) => card.kind !== "epic");
  const matchingEpicIds = new Set(tasks.map((card) => card.epicId).filter(Boolean) as string[]);
  const groups: EpicGroup[] = epics
    .filter((epic) => visibleIds.has(epic.id) || matchingEpicIds.has(epic.id))
    .map((epic) => ({
      id: epic.id,
      title: epic.title,
      description: epic.nextAction || epic.description || "No epic summary",
      epic,
      cards: tasks.filter((card) => card.epicId === epic.id).sort(compareByUpdated)
    }));

  const unassigned = tasks.filter((card) => !card.epicId || !epics.some((epic) => epic.id === card.epicId)).sort(compareByUpdated);
  if (unassigned.length > 0 || groups.length === 0) {
    groups.push({
      id: "no-epic",
      title: "No Epic",
      description: "Tasks that are not grouped under an epic yet.",
      cards: unassigned
    });
  }
  return groups;
}

function compareByUpdated(a: KanbanCard, b: KanbanCard): number {
  return Date.parse(b.updatedAt) - Date.parse(a.updatedAt);
}

function nextStatus(status: CardStatus): CardStatus {
  const index = statusOrder.indexOf(status);
  return statusOrder[Math.min(index + 1, statusOrder.length - 1)] ?? "done";
}

function columnLabel(status: CardStatus): string {
  return COLUMN_DEFINITIONS.find((column) => column.id === status)?.shortLabel ?? status;
}
