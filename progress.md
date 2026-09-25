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
7. Persist conversation history per user/session so `/ask` supports true multi-turn follow-up (e.g. answering "yes" to a recommended option) instead of rebuilding `messages` fresh every call.
   - Added `Conversation` and `ConversationMessage` SQLModel tables (`backend/main.py`) — confirmed auto-created in Neon Postgres via `create_tables()`. Applied by Hardeep.
   - `/ask` endpoint itself is **not yet updated** to read/write these tables — still rebuilds `messages` from scratch every call, `conversation_id` is not accepted or returned yet. Proposed full rewrite (load history if `conversation_id` given, else create new `Conversation`, persist every turn, return `conversation_id` in response) discussed but not applied — next step.
8. Once #7's `/ask` rewrite lands: update `SYSTEM_PROMPT` to ask clarifying questions one at a time (time period first, category only after the user answers) instead of combining both into a single message — this only makes sense once real conversation history exists.
