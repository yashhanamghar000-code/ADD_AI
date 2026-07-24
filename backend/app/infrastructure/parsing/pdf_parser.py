"""
PDF parsing strategy: pdfplumber layout pass -> pypdf rotation-normalized
fallback -> OCR (fitz + pytesseract) last resort, parallelized per-page
with a ThreadPoolExecutor. This is a faithful port of the original
project's page-processing algorithm — the logic is unchanged, only its
location and packaging (as one Strategy implementing IDocumentParser).
"""
import concurrent.futures
import os
from functools import partial
from typing import Dict, List, Optional

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image
from pypdf import PdfReader

from app.core.entities.document import DocumentChunk
from app.core.interfaces.document_parser import IDocumentParser


class PdfDocumentParser(IDocumentParser):

    def __init__(self, max_workers: int):
        self._max_workers = max_workers

    def supports(self, file_extension: str) -> bool:
        return file_extension == ".pdf"

    def parse(self, file_path: str, file_name: str, tenant_metadata: Dict[str, str]) -> List[DocumentChunk]:
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)
        except Exception as e:
            print(f"Failed to read PDF pages: {e}")
            return []

        if total_pages == 0:
            return []

        print(f"[Thread Parser] {total_pages} pages across up to {self._max_workers} thread workers...")

        # Small documents: skip pool overhead entirely for a 1-2 page file
        if total_pages <= 2 or self._max_workers <= 1:
            results = [
                self._parse_page(file_path, file_name, tenant_metadata, p)
                for p in range(1, total_pages + 1)
            ]
            return [r for r in results if r is not None]

        worker_fn = partial(self._parse_page, file_path, file_name, tenant_metadata)
        page_numbers = list(range(1, total_pages + 1))
        parsed_pages: List[DocumentChunk] = []

        # ThreadPoolExecutor sidesteps cross-platform multiprocessing
        # serialization issues entirely.
        with concurrent.futures.ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            for res in executor.map(worker_fn, page_numbers):
                if res is not None:
                    parsed_pages.append(res)

        # executor.map preserves entry order chronology seamlessly.
        return parsed_pages

    # ------------------------------------------------------------------
    # Per-page worker. Each call re-opens the file from disk by path
    # (file handles/state can't be safely shared across threads once we
    # start mutating page rotation), which is why this opens its own
    # handles instead of sharing one from the caller.
    # ------------------------------------------------------------------
    def _parse_page(
        self,
        file_path: str,
        file_name: str,
        tenant_metadata: Dict[str, str],
        page_num: int,
    ) -> Optional[DocumentChunk]:
        try:
            tables = []
            raw_text = ""
            image_summary_context = ""
            used_fallback = False
            needs_forced_rotation = False
            has_images = False

            # --- STEP 1: pdfplumber pass — layout inspection + normal extraction ---
            with pdfplumber.open(file_path) as pdf:
                if page_num > len(pdf.pages):
                    return None
                page = pdf.pages[page_num - 1]

                try:
                    has_images = len(page.images) > 0 or len(page.rects) > 15
                    if has_images:
                        image_summary_context = "\n[Visual Content Note: Page contains embedded visual layers.]"

                    # Landscape-shaped page is often a rotated portrait page
                    # (common in financial-report scans/exports).
                    if page.width > page.height:
                        needs_forced_rotation = True
                    else:
                        chars = page.chars
                        if chars and len(chars) > 100:
                            sampled_chars = chars[::20]
                            vertical_chars = sum(
                                1 for c in sampled_chars
                                if c.get("orientation") in ["up", "down"] or c.get("upright") == 0
                            )
                            if vertical_chars / len(sampled_chars) > 0.30:
                                needs_forced_rotation = True
                except Exception:
                    # If pdfplumber trips on a layout/index error, skip
                    # straight to the pypdf rotation-normalized path below.
                    needs_forced_rotation = False
                    used_fallback = True

                # --- STEP 2: native rotation check + correction via pypdf ---
                # A fresh PdfReader is opened here (rather than shared
                # across threads) because pypdf_page.rotate() mutates page
                # state; sharing one reader across workers risks one
                # thread's rotation bleeding into another's page.
                pypdf_page = None
                native_rotation = 0
                try:
                    local_reader = PdfReader(file_path)
                    pypdf_page = local_reader.pages[page_num - 1]
                    native_rotation = pypdf_page.get("/Rotate", 0)
                except Exception:
                    print(f"   ⚠️ Page {page_num}: Could not fetch page rotation metadata.")

                if (native_rotation in [90, 270] or needs_forced_rotation) and pypdf_page is not None and not used_fallback:
                    rotation_angle = (360 - native_rotation) if native_rotation in [90, 270] else 90
                    print(f"   -> Page {page_num}: Adjusting layout by {rotation_angle}° to normalize horizontal reading axis...")
                    try:
                        pypdf_page.rotate(rotation_angle)
                        raw_text = pypdf_page.extract_text() or ""
                        used_fallback = True
                    except Exception as e:
                        print(f"   ⚠️ Rotation parsing stream bottleneck on Page {page_num}: {e}")

                # --- STEP 3: normal extraction path if rotation wasn't needed ---
                if not used_fallback:
                    try:
                        tables = page.extract_tables()
                        raw_text = page.extract_text() or ""
                    except Exception:
                        print(f"   ⚠️ Layout stream bottleneck on Page {page_num}. Executing recovery...")
                        try:
                            if pypdf_page is not None:
                                raw_text = pypdf_page.extract_text() or ""
                                used_fallback = True
                        except Exception:
                            print(f"   ❌ Critical Error: Page {page_num} unreadable. Skipping.")
                            return None

                # --- STEP 4: last-resort recovery if fallback path produced nothing ---
                if used_fallback and not raw_text and pypdf_page is not None:
                    try:
                        raw_text = pypdf_page.extract_text() or ""
                    except Exception:
                        print(f"   ❌ Critical Recovery Error: Page {page_num} completely unparseable.")
                        return None

            # --- STEP 5: OCR fallback only when extracted text is genuinely poor/missing ---
            # Uses image_to_data (word-level bounding boxes) instead of
            # image_to_string (flat text) so citations can later highlight
            # the exact region on scanned pages that have no embedded PDF
            # text layer at all — plain OCR text alone gives pdf.js nothing
            # to search/highlight against on the client.
            ocr_words: List[Dict] = []
            page_width_pt = page_height_pt = None
            if len(raw_text.strip()) < 50:
                try:
                    with fitz.open(file_path) as fitz_doc:
                        fitz_page = fitz_doc.load_page(page_num - 1)
                        page_width_pt = fitz_page.rect.width
                        page_height_pt = fitz_page.rect.height
                        zoom = 150 / 72
                        pix = fitz_page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                        data = pytesseract.image_to_data(
                            img, config="--psm 6", output_type=pytesseract.Output.DICT
                        )
                        n = len(data["text"])
                        words_out = []
                        for i in range(n):
                            word = data["text"][i].strip()
                            conf_raw = data.get("conf", ["-1"] * n)[i]
                            conf = int(conf_raw) if str(conf_raw).lstrip("-").isdigit() else -1
                            if not word or conf < 30:
                                continue
                            # image pixel space -> PDF point space (divide
                            # by zoom); y flipped since image origin is
                            # top-left but PDF page origin is bottom-left.
                            x_px, y_px = data["left"][i], data["top"][i]
                            w_px, h_px = data["width"][i], data["height"][i]
                            x0 = x_px / zoom
                            x1 = (x_px + w_px) / zoom
                            y1 = page_height_pt - (y_px / zoom)
                            y0 = page_height_pt - ((y_px + h_px) / zoom)
                            words_out.append({
                                "text": word,
                                "x0": round(x0, 2), "y0": round(y0, 2),
                                "x1": round(x1, 2), "y1": round(y1, 2),
                            })

                        ocr_text = " ".join(w["text"] for w in words_out)
                        if len(ocr_text.strip()) > len(raw_text.strip()):
                            raw_text = ocr_text
                            ocr_words = words_out
                            image_summary_context += "\n[System Note: Text extracted via OCR.]"
                        img.close()
                except Exception as e:
                    print(f"OCR failed on page {page_num}: {e}")

            cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
            sanitized_text = "\n".join(cleaned_lines)

            table_markdown = ""
            if tables and not used_fallback:
                for table in tables:
                    cleaned_table = [[str(cell) if cell is not None else "" for cell in row] for row in table]
                    for row in cleaned_table:
                        if any(row):
                            table_markdown += "| " + " | ".join(row) + " |\n"
                    table_markdown += "\n"

            combined_content = f"ATTENTION LLM: FILE: '{file_name}' | PAGE: {page_num} {image_summary_context}\n" + sanitized_text
            if table_markdown:
                combined_content += "\n\n### Extracted Document Tables:\n" + table_markdown
            elif used_fallback:
                combined_content += "\n\n[System Note: Text structurally layout-normalized and parsed via horizontal fallback stream.]"

            return DocumentChunk(
                content=combined_content,
                metadata={
                    "source": file_name,
                    "page": page_num,
                    "has_table": bool(table_markdown),
                    "has_images": has_images,
                    "was_rotated": used_fallback,
                    "ocr_words": ocr_words or None,
                    "ocr_page_width": page_width_pt,
                    "ocr_page_height": page_height_pt,
                    **tenant_metadata,
                },
            )
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            return None