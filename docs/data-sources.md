# Data Sources and Data Flow

This document explains the data sources used in this coursework project and how they are used in the implemented features.

## 1. Data Sources Used

The project uses two practical data sources plus one optional enrichment input:

1. Local application data (SQLite)
- Stored in the project database (`backend/meal_api.db` by default).
- Includes user accounts, locally created/imported recipes, ratings, weekly plans, and suggestion cache.

2. External public recipe API (TheMealDB)
- Accessed at runtime through `app/services/themealdb.py`.
- Used for recipe discovery, cook details, external ratings, and weekly-plan candidate generation.

3. Optional dataset import and enrichment files
- Curated Food.com-style recipe subset files imported via `scripts/import_curated_recipes.py`.
- Optional USDA-style sidecar file for nutrition enrichment (calories/macros/allergens/cost estimate).

## 2. What Is Local vs External

### Local data
- User-generated recipes (`recipes` table):
  - core fields: title, cuisine, prep time, ingredients, steps, tags
  - nutrition fields (optional): calories, protein, carbs, fat, allergens, cost estimate
- User behavior data:
  - local recipe ratings
  - external recipe ratings (stored locally as references to external IDs)
  - weekly plans and per-day selections
  - cached recommendation payloads for performance

### External data
- TheMealDB recipes are fetched on demand and normalized into internal response schemas.
- The project does not fully mirror TheMealDB into local persistent recipe rows by default.
- External records can appear in Discover/Suggested/Cook responses and weekly-plan options.

## 3. Importing and Seeding Recipe Data

The project supports three lightweight ingestion paths:

1. Manual local entry (API/UI)
- Users create recipes directly.
- This is the most controlled source for recommendation quality in this project.

2. URL parser import (single recipe preview)
- Endpoint: `POST /api/v1/recipes/import-url`
- Parses public recipe pages (JSON-LD and simple HTML fallback) into preview fields.
- Intended as a helper for creating local recipes, not bulk ingestion.

3. Curated dataset import script (bulk)
- Command: `python scripts/import_curated_recipes.py --source <file> [--usda <file>]`
- Supports `.jsonl`, `.ndjson`, `.json`, `.csv`.
- Maps Food.com-style records to local `recipes` rows.
- Optional USDA-style sidecar enriches nutrition/allergen/cost fields.
- Includes practical duplicate skipping for imported owner records.

## 4. Known Dataset and Data-Quality Limitations

This section intentionally states limits to avoid overclaiming:

1. TheMealDB nutritional completeness
- TheMealDB integration currently has sparse nutrition metadata (often no calories/macros).
- Therefore, nutrition-driven analytics and recommendations are strongest on local/imported recipes with populated nutrition fields.

2. Curated subset bias
- Bulk import uses a curated subset, not the full upstream corpus.
- Any cuisine/tag/macro distribution can reflect curation choices rather than population-level food diversity.

3. Heuristic mapping assumptions
- Food.com-style nutrition list positions are interpreted by lightweight mapping logic.
- If source format changes, macro interpretation can degrade without schema-specific remapping.

4. No claim of clinical nutrition accuracy
- Nutrition values are used as product features for recommendation/planning signals.
- The system is not validated for medical, dietary, or regulatory advice.

5. Cold-start and sparse-history constraints
- Recommendation and analytics quality improves with more user ratings and richer recipe metadata.
- Users with minimal ratings/history receive weaker personalization signals.

## 5. How Data Supports Key Features

### Recommendation (`GET /api/v1/recipes/suggested`)
- Inputs:
  - local ratings + external ratings
  - local recipe metadata and optional nutrition fields
  - TheMealDB candidate results
- Signals used:
  - liked/disliked feature overlap (cuisine/tags/ingredients)
  - ingredient weighting with rarity adjustment
  - prep-time and calorie affinity
  - prep/calorie proximity and macro-profile affinity when nutrition exists
- Output:
  - ranked candidate list with explainability reasons
  - cached per user for efficiency

### Weekly planning (`POST /api/v1/users/me/weekly-plan/generate`)
- Candidate pool combines local and TheMealDB options.
- Plan builder applies practical constraints:
  - avoid consecutive repeated main ingredients
  - cap over-repeated cuisines
  - weekday quick-meal bias
  - weekend flexibility/treat bias
- Persists one local + one external option per day with user selection state.

### Analytics endpoints (`/users/me/analytics/*`)
- Derived from local ratings, external ratings, local recipes, and active weekly plan data.
- Includes taste profile, preference ranges, diversity, and nutrition summaries.
- Accuracy depends on available metadata (especially nutrition completeness).

## 6. Academic Positioning

For coursework purposes, this project uses a transparent hybrid data strategy:
- A stable local relational store for user and operational data.
- A real public external API for discoverability and variety.
- A reproducible import path for curated public datasets with optional enrichment.

This supports reproducibility and practical evaluation, while acknowledging limits in external nutrition coverage and curation bias.
