import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { KanbanStore, KanbanStoreError } from "../shared/store.js";
const app = express();
const port = Number(process.env.PORT ?? 3100);
const host = process.env.HOST ?? "127.0.0.1";
app.use(express.json({ limit: "1mb" }));
app.use((req, res, next) => {
    res.setHeader("Access-Control-Allow-Origin", "http://127.0.0.1:3001");
    res.setHeader("Access-Control-Allow-Headers", "Content-Type");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,PATCH,OPTIONS");
    if (req.method === "OPTIONS") {
        res.sendStatus(204);
        return;
    }
    next();
});
app.get("/api/health", asyncHandler(async (req) => {
    const store = storeForReq(req);
    return {
        ok: true,
        service: "agent-kanban",
        dataPath: store.path,
        now: new Date().toISOString()
    };
}));
app.get("/api/board", asyncHandler(async (req) => {
    const store = storeForReq(req);
    const board = await store.getBoard();
    const metrics = await store.getMetrics();
    return { board, metrics };
}));
app.get("/api/context", asyncHandler(async (req) => {
    const store = storeForReq(req);
    return store.getContext({
        cwd: asString(req.query.cwd),
        branch: asString(req.query.branch),
        agentSessionId: asString(req.query.agentSessionId),
        includeDone: asBoolean(req.query.includeDone),
        limit: asNumber(req.query.limit)
    });
}));
app.get("/api/cards", asyncHandler(async (req) => {
    const store = storeForReq(req);
    const filters = {
        status: asString(req.query.status),
        project: asString(req.query.project),
        cwd: asString(req.query.cwd),
        branch: asString(req.query.branch),
        tag: asString(req.query.tag),
        assigneeKind: asString(req.query.assigneeKind),
        query: asString(req.query.query),
        includeDone: asBoolean(req.query.includeDone),
        limit: asNumber(req.query.limit),
        offset: asNumber(req.query.offset)
    };
    return store.listCards(filters);
}));
app.post("/api/cards", asyncHandler(async (req) => storeForReq(req).createCard(req.body)));
app.post("/api/cards/:id/claim", asyncHandler(async (req) => storeForReq(req).claimCard({ ...req.body, cardId: req.params.id })));
app.post("/api/cards/:id/move", asyncHandler(async (req) => storeForReq(req).moveCard({ ...req.body, cardId: req.params.id })));
app.post("/api/cards/:id/progress", asyncHandler(async (req) => storeForReq(req).appendProgress({ ...req.body, cardId: req.params.id })));
app.post("/api/cards/:id/block", asyncHandler(async (req) => storeForReq(req).blockCard({ ...req.body, cardId: req.params.id })));
app.post("/api/cards/:id/complete", asyncHandler(async (req) => storeForReq(req).completeCard({ ...req.body, cardId: req.params.id })));
app.post("/api/sessions/start", asyncHandler(async (req) => storeForReq(req).startSession(req.body)));
app.post("/api/sessions/end", asyncHandler(async (req) => storeForReq(req).endSession(req.body)));
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const webDir = path.resolve(__dirname, "../web");
app.use(express.static(webDir));
app.get("*", (_req, res) => {
    res.sendFile(path.join(webDir, "index.html"));
});
app.use((err, _req, res, _next) => {
    if (err instanceof KanbanStoreError) {
        res.status(err.statusCode).json({ error: err.message });
        return;
    }
    const message = err instanceof Error ? err.message : "Unexpected server error";
    res.status(500).json({ error: message });
});
app.listen(port, host, () => {
    console.log(`Agent Kanban API listening at http://${host}:${port}`);
    console.log(`Default data path: ${KanbanStore.forCwd().path}`);
});
function asyncHandler(handler) {
    return (req, res, next) => {
        Promise.resolve(handler(req, res))
            .then((result) => {
            if (!res.headersSent)
                res.json(result);
        })
            .catch(next);
    };
}
function asString(value) {
    if (typeof value === "string" && value.trim())
        return value.trim();
    return undefined;
}
function asNumber(value) {
    if (typeof value !== "string" || !value.trim())
        return undefined;
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : undefined;
}
function asBoolean(value) {
    if (value === "true")
        return true;
    if (value === "false")
        return false;
    return undefined;
}
function storeForReq(req) {
    const body = typeof req.body === "object" && req.body !== null ? req.body : {};
    return KanbanStore.forCwd(asString(body.cwd) ?? asString(req.query.cwd));
}
