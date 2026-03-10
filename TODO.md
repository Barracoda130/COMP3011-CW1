# TODO

## Phase 1: Foundation and Submission Framing

- [x] Finalize project scope statement in `README.md` (MVP vs Stretch).
- [x] Lock database strategy for submission (`SQLite` with rationale or `PostgreSQL` with deployment).
- [x] Define target data model changes (weekly plans, taste profile storage, explanation fields).

## Phase 2: Schema Safety and Migration Discipline

- [ ] Add Alembic and create baseline migration setup.
- [ ] Add migrations for existing recent changes (`steps`, `intro`, `ingredients`).
- [ ] Add migrations for upcoming weekly-planning tables.
- [ ] Reduce startup schema patching in `init_db.py` once migrations are the source of truth.

## Phase 3: Core Feature Gap (Highest Mark Impact)

- [ ] Implement weekly plan models:
  - [ ] `weekly_plans`
  - [ ] `weekly_plan_items`
- [ ] Implement endpoints:
  - [ ] `POST /users/me/weekly-plan/generate`
  - [ ] `GET /users/me/weekly-plan/current`
- [ ] Apply planning constraints:
  - [ ] avoid consecutive same main ingredient
  - [ ] cap repeated cuisines
  - [ ] weekday quick-meal bias
  - [ ] weekend flexible/treat meal behavior

## Phase 4: Recommendation Quality Upgrade

- [ ] Extend taste-learning signals:
  - [ ] liked/disliked ingredients
  - [ ] prep-time preference bands
  - [ ] calorie preference bands
- [ ] Add explainable recommendations with a `reasons` list per item.
- [ ] Expose recommendation explanations in API responses.

## Phase 5: Import Pipeline Enhancement

- [ ] Keep webpage import parser aligned with current `intro/ingredients/steps` separation.
- [ ] Add video import MVP (captions-first).
- [ ] Add fallback flow for manual transcript paste when extraction is unavailable.
- [ ] Parse transcript into `intro`, `ingredients`, `steps` using marker rules.

## Phase 6: Frontend Demo-Readiness

- [ ] Add weekly plan page/UI.
- [ ] Show recommendation explanations in suggested cards.
- [ ] Verify cook/suggested/create/edit UX remains consistent with latest model fields.

## Phase 7: Test and Reliability Pass

- [ ] Add parser tests for intro/steps split edge cases.
- [ ] Add tests for weekly-plan constraints and generation behavior.
- [ ] Add tests for recommendation explanation outputs.
- [ ] Add tests for import error paths and unsupported sources.
- [ ] Run full backend and frontend test suites and fix regressions.

## Phase 8: Documentation and Delivery Artifacts

- [ ] Update README schema and endpoint examples to match current API shape.
- [ ] Add architecture + recommendation flow summary.
- [ ] Export API documentation to PDF and link it in README.
- [ ] Add deployment runbook (env vars, migrate, seed, start).

## Phase 9: Viva Preparation

- [ ] Prepare design trade-off notes:
  - [ ] FastAPI choice
  - [ ] recommendation method choice
  - [ ] data model/normalization trade-offs
  - [ ] DB choice justification
  - [ ] migration strategy
- [ ] Prepare known limitations + next-step roadmap for Q&A.
