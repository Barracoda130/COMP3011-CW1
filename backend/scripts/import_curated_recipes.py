from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running the script directly from backend/scripts.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal
from app.services.dataset_import import (
    DatasetImportError,
    count_recipes_for_owner,
    get_or_create_import_user,
    import_curated_foodcom_subset,
    iter_source_records,
    load_usda_enrichment,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a curated subset of public recipe data into local recipes table.",
    )
    parser.add_argument("--source", required=True, help="Path to source file (.jsonl/.ndjson/.json/.csv)")
    parser.add_argument(
        "--usda",
        default=None,
        help="Optional USDA-style enrichment file keyed by recipe_id (calories/macros/allergens/cost)",
    )
    parser.add_argument("--limit", type=int, default=250, help="Maximum recipes to import")
    parser.add_argument("--owner-email", default="dataset-importer@local")
    parser.add_argument("--owner-name", default="Dataset Importer")
    parser.add_argument("--source-tag", default="dataset:foodcom")
    parser.add_argument("--dry-run", action="store_true", help="Parse and map records without writing to DB")
    parser.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Do not skip duplicates by (title, cuisine) for import owner",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.limit <= 0:
        parser.error("--limit must be greater than 0")

    db = SessionLocal()
    try:
        records = iter_source_records(args.source)
        usda_lookup = load_usda_enrichment(args.usda)
        owner = get_or_create_import_user(db, email=args.owner_email, full_name=args.owner_name)

        before_count = count_recipes_for_owner(db, owner.id)
        stats = import_curated_foodcom_subset(
            db,
            records=records,
            owner=owner,
            limit=args.limit,
            usda_enrichment_by_source_id=usda_lookup,
            source_tag=args.source_tag,
            skip_duplicates=not args.allow_duplicates,
            dry_run=args.dry_run,
        )
        after_count = before_count if args.dry_run else count_recipes_for_owner(db, owner.id)

    except DatasetImportError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Import failed unexpectedly: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    print("Import summary")
    print(f"- owner_email: {args.owner_email}")
    print(f"- scanned: {stats.scanned}")
    print(f"- imported: {stats.imported}")
    print(f"- skipped_invalid: {stats.skipped_invalid}")
    print(f"- skipped_duplicate: {stats.skipped_duplicate}")
    print(f"- recipes_before: {before_count}")
    print(f"- recipes_after: {after_count}")
    print(f"- dry_run: {args.dry_run}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
