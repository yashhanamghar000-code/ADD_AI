/**
 * src/components/citation/CitationPdfPanel.jsx
 *
 * The right-side panel: renders the ORIGINAL PDF for the cited file,
 * scrollable, auto-scrolled to the cited page, with the matched snippet
 * highlighted on that page.
 *
 * For normal (text-layer) pages, highlighting is done client-side by
 * searching pdf.js's extracted text content for `citation.snippet`.
 *
 * For OCR'd/scanned pages, there IS no embedded PDF text layer to search
 * (pdf.js's getTextContent() returns nothing useful), so the backend
 * instead computes the exact highlight region from OCR word bounding
 * boxes and sends it as `citation.bbox` (in PDF point space, along with
 * `citation.page_width`/`page_height`) — this component draws that
 * directly instead of attempting a text search.
 *
 * Needs `pdfjs-dist`:
 *   npm install pdfjs-dist
 */
import React, { useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import { getAuthHeaders, getDocumentFileUrl } from "../../lib/citationApi";
import { computeHighlightRects, findMatchingItemIndices } from "../../lib/pdfTextHighlight";

// pdf.js needs its worker script. The CDN URL below matches whatever
// pdfjs-dist version npm installs, so it stays in sync automatically and
// needs zero bundler configuration. Swap for a locally-bundled worker
// later if you need fully offline support.
pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;

const RENDER_SCALE = 1.4;

export default function CitationPdfPanel({ citation, onClose }) {
  const [pdfDoc, setPdfDoc] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const scrollContainerRef = useRef(null);
  const pageRefs = useRef({}); // pageNumber -> HTMLDivElement

  const fileId = citation?.file_id;
  const targetPage = Number(citation?.page) || 1;
  const snippet = citation?.snippet || "";

  // Load the document whenever the citation's file changes.
  useEffect(() => {
    if (!fileId) return;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setPdfDoc(null);
    pageRefs.current = {};

    const loadingTask = pdfjsLib.getDocument({
      url: getDocumentFileUrl(fileId),
      httpHeaders: getAuthHeaders(),
    });

    loadingTask.promise
      .then((doc) => {
        if (cancelled) return;
        setPdfDoc(doc);
        setNumPages(doc.numPages);
        setLoading(false);
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Failed to load citation PDF:", err);
        setError("Could not load this document. It may have been removed.");
        setLoading(false);
      });

    return () => {
      cancelled = true;
      loadingTask.destroy?.();
    };
  }, [fileId]);

  // Once loaded, scroll to the target page.
  useEffect(() => {
    if (!pdfDoc) return;
    const el = pageRefs.current[targetPage];
    if (el && scrollContainerRef.current) {
      // Small delay lets the target page (and a couple neighbors) finish
      // their render pass before we scroll, so layout heights are final.
      const t = setTimeout(() => {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 150);
      return () => clearTimeout(t);
    }
  }, [pdfDoc, targetPage]);

  if (!citation) return null;

  return (
    <div style={styles.panel}>
      <div style={styles.header}>
        <div style={styles.headerText}>
          <div style={styles.title} title={citation.source}>{citation.source || "Document"}</div>
          <div style={styles.subtitle}>Page {targetPage}</div>
        </div>
        <button style={styles.closeButton} onClick={onClose} aria-label="Close citation viewer">
          ✕
        </button>
      </div>

      <div style={styles.body} ref={scrollContainerRef}>
        {loading && <div style={styles.centerMessage}>Loading document…</div>}
        {error && <div style={styles.centerMessageError}>{error}</div>}

        {pdfDoc &&
          Array.from({ length: numPages }, (_, i) => i + 1).map((pageNumber) => (
            <PdfPage
              key={pageNumber}
              pdfDoc={pdfDoc}
              pageNumber={pageNumber}
              isTarget={pageNumber === targetPage}
              snippet={pageNumber === targetPage ? snippet : ""}
              bbox={pageNumber === targetPage ? citation.bbox : null}
              pageWidthPt={citation.page_width}
              pageHeightPt={citation.page_height}
              registerRef={(el) => (pageRefs.current[pageNumber] = el)}
            />
          ))}
      </div>
    </div>
  );
}

/**
 * One page: renders its canvas, and — only on the target page — overlays
 * a highlight for the matched snippet. Uses citation.bbox directly when
 * present (OCR'd pages); otherwise falls back to searching pdf.js's text
 * layer for `snippet` (normal, non-scanned pages).
 */
function PdfPage({ pdfDoc, pageNumber, isTarget, snippet, bbox, pageWidthPt, pageHeightPt, registerRef }) {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const [highlightRects, setHighlightRects] = useState([]);
  const [rendered, setRendered] = useState(false);

  useEffect(() => {
    let cancelled = false;

    pdfDoc.getPage(pageNumber).then(async (page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale: RENDER_SCALE });

      const canvas = canvasRef.current;
      if (!canvas) return;
      const context = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;

      await page.render({ canvasContext: context, viewport }).promise;
      if (cancelled) return;
      setRendered(true);

      if (!isTarget) return;

      // OCR'd/scanned pages: use the exact bbox the backend computed
      // from OCR word coordinates, converting PDF point space straight
      // to canvas pixels using the same scale pdf.js applied above (and
      // flipping Y, since PDF's origin is bottom-left but canvas/DOM is
      // top-left).
      if (bbox && pageWidthPt && pageHeightPt) {
        const scaleX = viewport.width / pageWidthPt;
        const scaleY = viewport.height / pageHeightPt;
        setHighlightRects([
          {
            left: bbox.x0 * scaleX,
            top: (pageHeightPt - bbox.y1) * scaleY,
            width: (bbox.x1 - bbox.x0) * scaleX,
            height: (bbox.y1 - bbox.y0) * scaleY,
          },
        ]);
        return;
      }

      // Normal pages: search the embedded text layer for the snippet.
      if (snippet) {
        const textContent = await page.getTextContent();
        if (cancelled) return;
        const matchedIndices = findMatchingItemIndices(textContent, snippet);
        if (matchedIndices.length > 0) {
          setHighlightRects(computeHighlightRects(textContent, matchedIndices, viewport));
        }
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, pageNumber, isTarget, snippet, bbox, pageWidthPt, pageHeightPt]);

  return (
    <div
      ref={(el) => {
        containerRef.current = el;
        registerRef(el);
      }}
      style={{
        ...styles.pageContainer,
        ...(isTarget ? styles.targetPageContainer : {}),
      }}
    >
      <div style={styles.pageLabel}>Page {pageNumber}</div>
      <div style={{ position: "relative", display: "inline-block" }}>
        <canvas ref={canvasRef} style={styles.canvas} />
        {rendered &&
          highlightRects.map((rect, i) => (
            <div
              key={i}
              style={{
                position: "absolute",
                left: rect.left,
                top: rect.top,
                width: rect.width,
                height: rect.height,
                backgroundColor: "rgba(255, 224, 102, 0.55)",
                borderRadius: 2,
                pointerEvents: "none",
              }}
            />
          ))}
      </div>
    </div>
  );
}

const styles = {
  panel: {
    position: "fixed",
    top: 0,
    right: 0,
    height: "100vh",
    width: "min(480px, 92vw)",
    backgroundColor: "#ffffff",
    borderLeft: "1px solid #e5e7eb",
    boxShadow: "-4px 0 16px rgba(0,0,0,0.08)",
    display: "flex",
    flexDirection: "column",
    zIndex: 1000,
  },
  header: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "12px 16px",
    borderBottom: "1px solid #e5e7eb",
    flexShrink: 0,
  },
  headerText: { minWidth: 0 },
  title: {
    fontSize: 14,
    fontWeight: 600,
    color: "#111827",
    whiteSpace: "nowrap",
    overflow: "hidden",
    textOverflow: "ellipsis",
  },
  subtitle: { fontSize: 12, color: "#6b7280", marginTop: 2 },
  closeButton: {
    border: "none",
    background: "transparent",
    fontSize: 16,
    cursor: "pointer",
    color: "#6b7280",
    padding: 4,
    lineHeight: 1,
  },
  body: {
    flex: 1,
    overflowY: "auto",
    padding: 16,
    backgroundColor: "#f3f4f6",
  },
  centerMessage: { textAlign: "center", color: "#6b7280", marginTop: 40, fontSize: 14 },
  centerMessageError: { textAlign: "center", color: "#dc2626", marginTop: 40, fontSize: 14 },
  pageContainer: {
    marginBottom: 16,
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
  targetPageContainer: {
    outline: "2px solid #6366f1",
    outlineOffset: 4,
    borderRadius: 6,
  },
  pageLabel: { fontSize: 11, color: "#9ca3af", marginBottom: 4 },
  canvas: {
    boxShadow: "0 1px 4px rgba(0,0,0,0.15)",
    maxWidth: "100%",
    height: "auto",
  },
};