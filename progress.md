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

## Open items / next up
1. Fix single-round tool-calling bug in `/ask` (root cause of null answers).
2. Add category `enum` to `expense_tools` schema.
3. Handle unrecognized `date_range` phrases (e.g. "last quarter") instead of silently ignoring the filter.
4. Remove leftover `DEBUG print(...)` statements added during troubleshooting.
5. Consider raising `max_tokens` (currently 1000 on both completion calls) since the reasoning model spends tokens on `reasoning_content` before final `content`.
