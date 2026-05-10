---
name: reviewers
description: Use this skill whenever the user asks to review, verify, or usability-test a web page, macOS app, or iOS Simulator app with reviewers; whenever a sprint gate needs LLM/persona-based UI behavior evidence; or whenever `review_target`, reviewers MCP, automated app review, harness review, persona review, web review, macOS review, or iOS app review is mentioned.
---

# Reviewers App Review

Use `reviewers` as the first-choice tool for persona-based product behavior review when the target is a web page, macOS app, or iOS Simulator app. This is for automated UX/behavior evidence; keep normal unit, integration, and Playwright tests for deterministic code checks.

Default to CLI for harnesses, sprint gates, and any repeated verification. Use MCP when an interactive LLM session needs tool discovery and direct tool calling.

## Preconditions

- The reviewers backend must be running locally, normally at `http://127.0.0.1:8787`.
- Default repo path is `~/projects/reviewers`; override with `REVIEWERS_ROOT` if needed.
- Default backend URL is `REVIEWERS_BACKEND_URL=http://127.0.0.1:8787`.
- Web targets use the reviewers Playwright helper.
- macOS and iOS targets need macOS Accessibility permission for the helper before snapshots/actions can work.

## Preferred Harness Path

For shell-based gates, call the reviewers CLI directly:

```sh
reviewers --json review-target \
  --url http://127.0.0.1:3000/settings \
  --goal "Change the profile display name to Alex and confirm the saved name is visible." \
  --success-criteria "The settings page shows the saved display name Alex after save." \
  --persona-preset it-novice \
  --score-threshold 7
```

When the `reviewers` binary is not installed, use the plugin adapter. It finds `REVIEWERS_CLI`, `~/projects/reviewers/target/debug/reviewers`, `reviewers` on PATH, or falls back to `cargo run`:

```sh
~/projects/kangnam-plugins/kangnam-dev/scripts/reviewers/review-target.py \
  --url http://127.0.0.1:3000/settings \
  --goal "Change the profile display name to Alex and confirm the saved name is visible." \
  --success-criteria "The settings page shows the saved display name Alex after save." \
  --persona-preset it-novice \
  --score-threshold 7
```

Exit codes:

- `0`: review completed and score is at least `--score-threshold`.
- `1`: review completed below threshold, got stuck, or failed.
- `2`: review timed out.
- `3`: setup/runtime error such as backend unreachable, invalid target, or missing persona.

## MCP Path

Call the reviewers MCP tool `review_target` with one concrete target and a concrete task:

```json
{
  "target_app": { "Url": "http://127.0.0.1:3000/settings" },
  "goal": "Change the profile display name to Alex and confirm the saved name is visible.",
  "success_criteria": "The settings page shows the saved display name Alex after save.",
  "persona": { "preset": "it-novice" },
  "max_steps": 30,
  "timeout_ms": 600000
}
```

Target shapes:

```json
{ "Url": "http://127.0.0.1:3000" }
{ "BundleId": "com.apple.TextEdit" }
{ "RunningApp": { "pid": 12345, "bundle_id": "com.apple.TextEdit" } }
{ "IosSimulator": { "udid": "SIMULATOR-UDID", "bundle_id": "com.example.app" } }
```

Persona presets: `it-novice`, `grandma-70`, `power-user`, `impatient-mobile-user`, `a11y-screen-reader`.

## Prompt Discipline

- Write `goal` as the exact task a user persona should attempt, not a broad feature label.
- Write `success_criteria` as an observable end state.
- Prefer one review per critical flow. Do not cram multiple flows into one `goal`.
- If login is required, pass `credentials` to MCP or `--username/--password` to the adapter; never paste secrets into progress memos.
- Report the reviewers score, status, key issues, and report URL when available.
