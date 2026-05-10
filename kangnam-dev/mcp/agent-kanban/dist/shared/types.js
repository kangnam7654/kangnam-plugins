export const COLUMN_DEFINITIONS = [
    { id: "backlog", label: "Backlog", shortLabel: "Backlog", intent: "Captured but not ready" },
    { id: "ready", label: "Ready", shortLabel: "Ready", intent: "Actionable next work" },
    { id: "in_progress", label: "In Progress", shortLabel: "Doing", intent: "Currently owned work" },
    { id: "review", label: "Review", shortLabel: "Review", intent: "Needs user or verification review" },
    { id: "blocked", label: "Blocked", shortLabel: "Blocked", intent: "Needs a decision or missing input" },
    { id: "done", label: "Done", shortLabel: "Done", intent: "Verified and complete" }
];
export const PRIORITIES = ["urgent", "high", "medium", "low"];
export const TEST_STATUSES = ["passed", "failed", "skipped"];
export const SESSION_OUTCOMES = ["continued", "blocked", "completed", "abandoned"];
