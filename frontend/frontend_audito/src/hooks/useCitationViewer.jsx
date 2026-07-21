/**
 * NEW FILE — copy into src/hooks/useCitationViewer.jsx
 *
 * Global open/close state for the citation viewer panel. Wrap your app
 * (or just the authenticated layout) with <CitationViewerProvider>, then
 * call useCitationViewer().open(citation) from anywhere a citation is
 * rendered (chat bubble, sidebar, wherever).
 */
import React, { createContext, useCallback, useContext, useMemo, useState } from "react";

const CitationViewerContext = createContext(null);

export function CitationViewerProvider({ children }) {
  const [activeCitation, setActiveCitation] = useState(null); // { file_id, page, snippet, source } | null

  const open = useCallback((citation) => {
    if (!citation?.file_id) {
      console.warn("Citation is missing file_id — cannot open PDF viewer.", citation);
      return;
    }
    setActiveCitation(citation);
  }, []);

  const close = useCallback(() => setActiveCitation(null), []);

  const value = useMemo(() => ({ activeCitation, open, close }), [activeCitation, open, close]);

  return (
    <CitationViewerContext.Provider value={value}>
      {children}
    </CitationViewerContext.Provider>
  );
}

export function useCitationViewer() {
  const ctx = useContext(CitationViewerContext);
  if (!ctx) {
    throw new Error("useCitationViewer must be used inside <CitationViewerProvider>");
  }
  return ctx;
}
