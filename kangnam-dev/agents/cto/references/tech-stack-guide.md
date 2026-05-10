# Tech Stack Guide

## Platform Defaults

| Layer | Default | Alternatives (score via Trade-Off) |
|---|---|---|
| Frontend (web) | Next.js (React) | Vite + React, Nuxt (Vue) |
| Backend | FastAPI (Python), Express (Node.js) | NestJS, Django |
| Database | PostgreSQL, Supabase | SQLite (prototype only) |
| Mobile | **React Native** | N/A |
| Infra | Vercel (web), AWS (backend) | GCP, Railway |
| Auth | Supabase Auth, NextAuth | Firebase Auth |

## Mobile: React Native Only

Flutter is **excluded from all consideration**. Do not include Flutter as a trade-off option. Do not score Flutter. If any input suggests Flutter, replace with React Native and note: "Flutter는 고려 대상에서 제외. React Native을 사용하라."

## Design Tool Mapping

| App type | Design tool |
|---|---|
| Web app (SPA, SSR, SSG) | HTML/CSS 목업 |
| Native app / React Native | Google Stitch MCP |
| Both web + mobile | HTML/CSS for web screens, Stitch MCP for mobile screens |

## Testing Tools Mapping

| Condition | `testing_tools.app_verification` |
|---|---|
| Web only (no mobile field or mobile = "N/A") | Reviewers MCP for persona review + Playwright for deterministic tests |
| Mobile = "React Native" | Reviewers MCP for iOS Simulator persona review |
| Both web + mobile | Reviewers MCP for web+iOS persona review + Playwright for deterministic tests |

Use reviewers for task-level behavior evidence from a persona's point of view.
Keep Playwright/unit tests for deterministic assertions that should run in CI.

## API Standard Defaults

| Setting | Default |
|---|---|
| Protocol | REST |
| Auth | JWT (via Supabase Auth or custom) |
| Versioning | URL path (`/api/v1/`) |
| Naming | snake_case (Python backend) or camelCase (Node.js backend) — match the backend language convention |
| Error format | `{ "error": { "code": "ERROR_CODE", "message": "Human-readable message" } }` |

Deviate from defaults only when the Trade-Off Framework score justifies it. Document deviation in an ADR.
