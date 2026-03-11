from __future__ import annotations

from pathlib import Path


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_pdf(lines: list[str]) -> bytes:
    content_lines = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
    first = True
    for line in lines:
        text = _escape_pdf_text(line)
        if first:
            content_lines.append(f"({text}) Tj")
            first = False
        else:
            content_lines.append(f"T* ({text}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1", errors="replace")

    objects: list[bytes] = []
    objects.append(b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n")
    objects.append(b"2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n")
    objects.append(
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>\nendobj\n"
    )
    objects.append(b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n")
    objects.append(
        b"5 0 obj\n<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n" + content_stream + b"\nendstream\nendobj\n"
    )

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(output))
        output.extend(obj)

    xref_pos = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    out_path = repo_root / "docs" / "api-documentation.pdf"

    lines = [
        "Meal Planner Pro API Documentation",
        "Base URL: /api/v1",
        "",
        "Auth",
        "POST /auth/register",
        "POST /auth/login",
        "GET /auth/me",
        "",
        "Recipes",
        "GET /recipes",
        "GET /recipes/mine",
        "GET /recipes/discover",
        "GET /recipes/cook/{source}/{recipe_id}",
        "GET /recipes/suggested",
        "GET /recipes/rated",
        "POST /recipes",
        "POST /recipes/import-url",
        "POST /recipes/{recipe_id}/copy",
        "GET /recipes/{recipe_id}",
        "PUT /recipes/{recipe_id}",
        "DELETE /recipes/{recipe_id}",
        "POST /recipes/{recipe_id}/ratings",
        "GET /recipes/{recipe_id}/ratings/me",
        "POST /recipes/themealdb/{external_recipe_id}/ratings",
        "GET /recipes/themealdb/{external_recipe_id}/ratings/me",
        "",
        "Users Weekly Plan",
        "POST /users/me/weekly-plan/generate",
        "GET /users/me/weekly-plan/current",
        "POST /users/me/weekly-plan/current/select",
        "",
        "For full interactive schema, run backend and open /docs.",
    ]

    pdf_bytes = build_simple_pdf(lines)
    out_path.write_bytes(pdf_bytes)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
