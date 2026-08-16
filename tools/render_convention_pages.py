"""Render the collective agreement as mobile-friendly JPEG pages."""

from pathlib import Path

import pymupdf


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "assets" / "convenio-77-89.pdf"
DESTINATION = ROOT / "assets" / "convenio-77-89-pages"


def main() -> None:
    DESTINATION.mkdir(parents=True, exist_ok=True)
    document = pymupdf.open(SOURCE)
    for index, page in enumerate(document, start=1):
        scale = 1080 / page.rect.width
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        pixmap.save(DESTINATION / f"page-{index:02d}.jpg", jpg_quality=76)
    print(f"Rendered {document.page_count} pages in {DESTINATION}")


if __name__ == "__main__":
    main()
