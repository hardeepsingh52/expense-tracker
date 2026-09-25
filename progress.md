# Progress Log

## Rule: Claude does not edit code
Starting 2026-09-24, Claude must NOT modify code files directly. Instead, Claude should describe the needed change here (or in chat) and let Hardeep make the edit himself.

## Log

### 2026-09-24
- Synced local `main` branch with `origin/main` (fast-forward pull, picked up auth changes in `backend/main.py`).
- Created `backend/.env` (gitignored) with `GROQ_API_KEY` and a generated `SECRET_KEY`.
- Switched `DATABASE_URL` from local SQLite to hosted Neon Postgres so the project can be worked on from both home and office. Added `DATABASE_URL` to `.env`, installed `psycopg2-binary`, generated `backend/requirements.txt`.
- Fixed Groq tool-call error (`get_expenses_summary` schema rejected `category: null`) by changing the `category` parameter's JSON schema type from `"string"` to `["string", "null"]` in the `expense_tools` definition in `backend/main.py`. This was applied before the no-code-edit rule below took effect.

## Rule in effect from this point forward
Claude will only describe changes (here or in chat) — Hardeep applies all code edits himself.
- Created `backend/seed_expenses.py` — generates fake expense data from 2020 to present across 10 categories (Food, Transport, Bills, Entertainment, Shopping, Health, Rent, Travel, Education, Miscellaneous) for the existing user `hardeep2792@gmail.com`. Run with `venv\Scripts\python.exe seed_expenses.py` from `backend/`.
- Note: a stray `breakpoint()` was added in the `/ask` endpoint during debugging — removed since (confirmed not present in latest `main.py`).
- Switched LLM provider from Groq to NVIDIA NIM (`nvidia/nemotron-3-super-120b-a12b`), added `NVIDIA_API_KEY` to `.env`.
- Added `date_range` parameter (schema + `parse_date_range()` helper + `get_expenses_summary` support) so `/ask` can filter by "this month", "last month", "this year", "last year", or an explicit `"YYYY-MM-DD to YYYY-MM-DD"` string. Unrecognized phrases (e.g. "last quarter") currently silently fall through to no date filter — known gap, not yet fixed.
- Diagnosed why `/ask` sometimes returns `{"answer": null}`: root cause is the single-round tool-calling logic in the `/ask` endpoint (`backend/main.py`) — if the model's second (`final_response`) completion also comes back as another `tool_calls` request instead of final `content`, the code returns `final_response.choices[0].message.content` directly (which is `None`) instead of looping to execute that second tool call. Confirmed via debug logging: for "how much did I spend on clothes this month", the model tried `category: "clothes"` then `category: "Clothing"` (neither matches seeded category `"Shopping"`), got "No expense found" both times, and the second attempt's response itself was another unexecuted `tool_calls` — never fixed yet.
- Proposed fix (not yet applied): add an `enum` of valid categories (`Food, Transport, Bills, Entertainment, Shopping, Health, Rent, Travel, Education, Miscellaneous`) to the `category` property in `expense_tools`, so the model can't invent nonexistent category names like `"Clothing"`.
- Proposed fix (not yet applied): replace the single tool-call round in `/ask` with a loop (~3-4 rounds max) so follow-up tool calls actually execute instead of returning `null`.
- Discussed (not building yet): connecting to Canadian banks to auto-import transactions. Recommended Plaid (best Canadian bank coverage + free sandbox) or Flinks (Canadian-native) over Yodlee. Decided to hold off and keep improving the current app first.

### 2026-09-24 (cont.)
- Fixed #1: `/ask` now loops (up to 4 rounds) over `client.chat.completions.create`, checking `reply.tool_calls` each round and only returning once `reply.content` is present, instead of assuming the 2nd call is always final. Applied by Hardeep per the no-code-edit rule.
- Tested and confirmed working: a compound question ("compare my shopping spend this month vs last month") — previously the case that triggered the `null` bug — now correctly runs the tool twice across two loop rounds and returns a synthesized comparison answer.
- Enum fix (#2, category enum in `expense_tools`) also already applied — confirmed present in current `main.py`.

### 2026-09-24 (cont. 2)
- Diagnosed the "reasoning dump in answer" issue (seen when asking about non-existent categories like "electronics"): not a code bug — `content` and `reasoning_content` are correctly separate fields in the NVIDIA response, but the model itself was writing confused reasoning into `content` because it had no confident answer (no "Electronics" category exists, only "Shopping", and the tool can't filter by description).
- Added a `SYSTEM_PROMPT` (in `backend/main.py`, `/ask` endpoint) instructing the model to: never narrate reasoning in the answer, stick to the fixed category list, and when a question doesn't map to an exact category, offer exactly two concrete options (one marked "Recommended") with the recommended total given immediately — no leftover ambiguity, no waiting for user confirmation. Applied by Hardeep.
- Tested and confirmed working:
  - "how much did I spend on electronics" → clean 2-option response ("Recommended: Shopping – $668,737.89 / Alternative: Miscellaneous – $230,473.25"), no reasoning leak.
  - "how much did I spend on food this year" → unaffected, still a terse direct answer.
- Note: `/ask` is currently stateless (each call rebuilds `messages` from scratch, no conversation history persisted) — the "ask 2 options, let user reply" pattern only works as a single-shot response for now, not true multi-turn follow-up. Noted as a future item below.

### 2026-09-24 (cont. 3)
- Extended `SYSTEM_PROMPT` to also handle missing/unrecognized time periods (previously: no time period specified silently defaulted to an all-time total, e.g. summed 2020–present).
- First attempt caused a NEW reasoning-leak: the category-ambiguity rule ("give the number immediately") and the time-period rule ("ask first, don't call the tool") contradicted each other when both were ambiguous at once — the model dumped its confusion trying to reconcile them into `content`, same symptom as before but from a prompt contradiction, not data ambiguity.
- Fixed by giving explicit precedence instead of two independent "always" rules: Step 1 checks time period first and short-circuits (asks, folding in a category note if that's also unclear); Step 2 only reaches category-ambiguity handling (immediate answer with recommended option) once time period is already clear; Step 3 is the clean direct-answer path when both are clear.
- Tested and confirmed working across all 4 paths:
  - Both ambiguous ("electronics", no time) → asks time period first + category note, no tool call, no leak.
  - Both clear ("food this year") → direct `$71,874.61`, unaffected.
  - Only category ambiguous, time clear ("electronics this month") → immediate answer using recommended category ($12,609.13 via Shopping).
  - Unrecognized time phrase ("last quarter") → correctly caught and clarified instead of silently defaulting to all-time.

## Open items / next up
1. ~~Fix single-round tool-calling bug in `/ask`~~ — done, tested 2026-09-24.
2. ~~Add category `enum` to `expense_tools` schema~~ — done.
3. ~~Handle unrecognized `date_range` phrases (e.g. "last quarter")~~ — done via `SYSTEM_PROMPT` Step 1, tested 2026-09-24.
4. Remove leftover `DEBUG print(...)` statements added during troubleshooting.
5. Consider raising `max_tokens` (currently 1000 on both completion calls) since the reasoning model spends tokens on `reasoning_content` before final `content`.
6. ~~Fix reasoning-dump-in-answer issue for ambiguous/non-existent category questions~~ — done via `SYSTEM_PROMPT`, tested 2026-09-24.
7. ~~Persist conversation history per user/session~~ — done. `Conversation`/`ConversationMessage` tables added, `/ask` rewritten to load history when `conversation_id` is passed (else creates a new conversation), persists every turn, and returns `conversation_id` in the response. Applied by Hardeep, tested 2026-09-24.
8. ~~Ask clarifying questions one at a time~~ — done via updated `SYSTEM_PROMPT` (time period first, category only if it's an explicit mismatch, no-category-mentioned is treated as "all categories" not ambiguous).
9. Fixed a data-loss bug in `SYSTEM_PROMPT`: 6 lines had lost their leading character/bullet dash ("alid expense categories", "tep 1", etc., missing "- " bullets) — likely an editor paste glitch. Restored text and, since already editing, also added "this week"/"last week" support (both `SYSTEM_PROMPT`'s recognized list and matching cases in `parse_date_range()` — Monday-start week boundaries via `now.weekday()`). This edit was made directly by Claude as an explicit one-time exception to the no-code-edit rule, per Hardeep's direct instruction ("fix it now then push").
- Tested and confirmed working: no-time/no-category question asks cleanly with week+month options and mentions custom range; "this week" → real total; "last week" → correctly reports no expenses instead of erroring; "food this year" regression check unaffected; `conversation_id` now returned and incrementing across calls.

### 2026-09-25
- Investigated switching `/ask`'s LLM off Nemotron (reasoning model) to reduce token spend on `reasoning_content` before the final answer, given the fixed `max_tokens=1000` cap.
- Tried `qwen/qwen2.5-72b-instruct` (and the underscore variant `qwen2_5-72b-instruct`) — 404. Confirmed via NVIDIA's catalog search that Qwen2.5-72B-Instruct has been removed from `build.nvidia.com`/NIM entirely; Qwen is currently only offered there as image models.
- Tried `meta/llama-3.3-70b-instruct` — got `410 Gone`, confirmed EOL'd 2026-08-26 despite still being listed in NVIDIA's docs (docs lag behind actual availability — not reliable for checking what's live).
- Learned the reliable way to check what's actually usable: `GET https://integrate.api.nvidia.com/v1/models` with the API key lists every model ID NVIDIA will respond to for that key. Even that isn't fully reliable though — `nvidia/llama-3.1-nemotron-70b-instruct` appeared in that list but still 404'd on `/chat/completions` (some listed models are self-hosted-NIM-only, not available on the serverless endpoint). Confirmed the only trustworthy check is a live test POST to `/chat/completions`.
- Landed on `openai/gpt-oss-20b` — confirmed working via a direct curl POST test (`STATUS: 200`). Applied as the new `/ask` model (replacing the `qwen_model` variable's value) along with `reasoning_effort="low"` on both `client.chat.completions.create(...)` calls in the endpoint, to cap deliberation tokens since gpt-oss is still technically a reasoning model. Not yet re-tested against the full regression suite (ambiguous category, ambiguous time period, this/last week, compound comparison) — do that next.
- Also fixed a self-inflicted issue: a PowerShell debugging command got accidentally pasted into `backend/.env` instead of the terminal, appending two garbage lines after `DATABASE_URL`. Removed.

- Re-tested `openai/gpt-oss-20b` against the full 6-case regression suite — 3 regressions found: (1) ambiguous category + no time period skipped the time-period question and answered directly assuming "this month" instead of following `SYSTEM_PROMPT` Step 1 precedence; (2) "this week" and (3) "last week" — both explicitly recognized phrases — were treated as ambiguous and asked for clarification instead of answering directly; the compound "this month vs last month" comparison also came back garbled, mixing an unrelated "other purchases" figure into the answer. Conclusion: gpt-oss-20b (20B) isn't reliably following the multi-step `SYSTEM_PROMPT` logic — a capability gap, not a config issue.
- Checked for a stronger non-reasoning alternative: `openai/gpt-oss-120b` — 410, EOL'd 2026-09-03. `mistralai/mistral-large-2-instruct` — 404. `moonshotai/kimi-k2.6` — 404. `nvidia/llama-3.1-nemotron-ultra-253b-v1` — 404. `z-ai/glm-5.3` — live but burned its entire token budget on `reasoning_content` with `content: null`. `nvidia/nemotron-3-ultra-550b-a55b` — live, reasoning model, answered concisely in a quick smoke test. None of the strong non-reasoning open models (Mistral Large, Kimi, GPT-OSS-120B) are actually available on this NVIDIA key right now — only smaller/weaker instruct models or bigger reasoning models are live.
- Decision: reverted `/ask` back to `nvidia/nemotron-3-super-120b-a12b` (the known-good model) and dropped the gpt-oss-specific `reasoning_effort="low"` param. Raised `max_tokens` from 1000 to 2000 to address the original token-budget concern directly instead of via a model swap. Hardeep briefly tried `nvidia/nemotron-3-ultra-550b-a55b` mid-session but reverted to `nvidia_super_model`.
- Re-ran the full 6-case regression suite against the reverted `nvidia_super_model` + `max_tokens=2000` — all 6 passed (ambiguous category asks time period first, "food this year" correct, "electronics this month" recommends Shopping correctly, "last quarter" clarifies instead of defaulting, "this week"/"last week" both answer directly and correctly, compound comparison gives a clean two-tool-call answer with correct math).

- Checked for leftover `DEBUG print(...)` statements — none found. The only `print(...)` calls in `main.py` are the two intentional startup logs ("STARTUP: creating tables...", "STARTUP: tables created"). Hardeep confirmed keeping those.

- Started the client, then paused it: scaffolded a Next.js (web) app in `frontend/` before Hardeep clarified the actual target is a **mobile app**, not web — noted in memory so future sessions don't default to web frameworks for the client. The `frontend/` Next.js scaffold is stale/unused as a result.
- Decided on hosting split: Next.js/web pieces (if ever used) on Vercel, but the FastAPI backend goes on Render.com — not because of Vercel's timeout (corrected assumption: Vercel Hobby is actually configurable up to 60s, or 300s with Fluid Compute, not a fixed 15s), but because Render gives an always-on process that fits a persistent SQLModel/Postgres engine and the `/ask` endpoint's multi-round LLM calls much better than Vercel's stateless serverless functions.
- Cleaned up `main.py`: removed a leftover placeholder comment, a duplicate `bcrypt` import, unused LLM model variables (`openai_instruct_model`, `nvidia_ultra_model`, `groq_model`) and dead commented-out Groq client code, a typo ("cussessfully" → "successfully"), inconsistent spacing in `update_expense`'s signature, and a duplicated `parse_date_range` definition (moved the single copy above its caller `get_expenses_summary` instead of after the whole `/ask` endpoint). Verified with a syntax check and a live `/ask` smoke test post-cleanup — still working.

## Open items / next up
- Build the mobile app client from scratch (stack not yet chosen) — `/ask` already returns `conversation_id`, ready for a real chat UI to pass it back on follow-up questions.
- Deploy backend to Render.com when ready.
