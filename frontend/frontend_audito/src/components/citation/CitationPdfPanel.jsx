/**
 * REPLACE your existing
 * src/components/citation/CitationPdfPanel.jsx with this file.
 *
 * v2 fixes vs. what you have:
 *
 * 1. ACCURATE SCROLL-TO-PAGE: previously, scrollIntoView fired on a fixed
 *    150ms timer, but pages render asynchronously and each one "pops in"
 *    at full height once its canvas finishes drawing — so pages ABOVE the
 *    target were still reflowing (pushing content down) after the scroll
 *    already happened, landing you slightly off. Now every page reserves
 *    its correct pixel height immediately (from PDF.js's viewport, which
 *    is known before rendering) via a placeholder div, so there's no
 *    layout shift, and we scroll only after the TARGET page itself has
 *    actually finished rendering (via a real completion callback, not a
 *    guessed timeout).
 *
 * 2. Uses the new fuzzy line-matching in pdfTextHighlight.js (v2) for
 *    more reliable, single-line highlight bars instead of scattered boxes.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import * as pdfjsLib from "pdfjs-dist";
import { getAuthHeaders, getDocumentFileUrl } from "../../lib/citationApi";
import { computeHighlightRects, findMatchingItemIndices } from "../../lib/pdfTextHighlight";

pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.mjs`;

const RENDER_SCALE = 1.4;

export default function CitationPdfPanel({ citation, onClose }) {
  const [pdfDoc, setPdfDoc] = useState(null);
  const [numPages, setNumPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const scrollContainerRef = useRef(null);
  const pageRefs = useRef({}); // pageNumber -> HTMLDivElement
  const hasScrolledRef = useRef(false);

  const fileId = citation?.file_id;
  const targetPage = Number(citation?.page) || 1;
  const snippet = citation?.snippet || "";

  useEffect(() => {
    if (!fileId) return;
    let cancelled = false;

    setLoading(true);
    setError(null);
    setPdfDoc(null);
    pageRefs.current = {};
    hasScrolledRef.current = false;

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

  // Called by the target PdfPage once ITS canvas has actually finished
  // rendering — this is the accurate trigger to scroll, instead of a
  // fixed timeout that races against every other page's render.
  const handleTargetPageReady = useCallback(() => {
    if (hasScrolledRef.current) return;
    const el = pageRefs.current[targetPage];
    if (el) {
      hasScrolledRef.current = true;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [targetPage]);

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
              registerRef={(el) => (pageRefs.current[pageNumber] = el)}
              onTargetRendered={pageNumber === targetPage ? handleTargetPageReady : undefined}
            />
          ))}
      </div>
    </div>
  );
}

function PdfPage({ pdfDoc, pageNumber, isTarget, snippet, registerRef, onTargetRendered }) {
  const canvasRef = useRef(null);
  const [highlightRects, setHighlightRects] = useState([]);
  const [rendered, setRendered] = useState(false);
  // Reserved BEFORE the canvas actually paints, from the page's viewport
  // (known synchronously, no need to wait for render()) — this is what
  // stops later-appearing pages from shifting earlier ones (and therefore
  // the target page) after a scroll has already happened.
  const [reservedSize, setReservedSize] = useState(null);

  useEffect(() => {
    let cancelled = false;

    pdfDoc.getPage(pageNumber).then(async (page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale: RENDER_SCALE });
      setReservedSize({ width: viewport.width, height: viewport.height });

      const canvas = canvasRef.current;
      if (!canvas) return;
      const context = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;

      await page.render({ canvasContext: context, viewport }).promise;
      if (cancelled) return;
      setRendered(true);

      if (isTarget && snippet) {
        const textContent = await page.getTextContent();
        if (cancelled) return;
        const matchedIndices = findMatchingItemIndices(textContent, snippet);
        if (matchedIndices.length > 0) {
          setHighlightRects(computeHighlightRects(textContent, matchedIndices, viewport));
        }
      }

      if (isTarget) {
        onTargetRendered?.();
      }
    });

    return () => {
      cancelled = true;
    };
  }, [pdfDoc, pageNumber, isTarget, snippet, onTargetRendered]);

  return (
    <div
      ref={registerRef}
      style={{
        ...styles.pageContainer,
        ...(isTarget ? styles.targetPageContainer : {}),
        // Reserve the exact final height up front so this page never
        // pops in and shifts pages below/above it after we've scrolled.
        minHeight: reservedSize ? reservedSize.height + 24 : undefined,
      }}
    >
      <div style={styles.pageLabel}>Page {pageNumber}</div>
      <div
        style={{
          position: "relative",
          display: "inline-block",
          width: reservedSize?.width,
          height: reservedSize?.height,
        }}
      >
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
                transition: "opacity 0.3s ease",
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
