/**
 * NEW FILE — copy into src/components/citation/CitationChip.jsx
 *
 * Small clickable citation pill. Use this wherever you currently render
 * citations under a chat answer instead of plain text — clicking it opens
 * the CitationPdfPanel via useCitationViewer().
 *
 * Example (in your chat message component, wherever you map over
 * `citations` from the /api/chat response):
 *
 *   import CitationChip from "../citation/CitationChip";
 *   ...
 *   {message.citations?.map((c, i) => (
 *     <CitationChip key={i} citation={c} />
 *   ))}
 */
import React from "react";
import { useCitationViewer } from "../../hooks/useCitationViewer";

export default function CitationChip({ citation }) {
  const { open } = useCitationViewer();

  if (!citation) return null;

  return (
    <button
      type="button"
      onClick={() => open(citation)}
      title={`Open ${citation.source}, page ${citation.page}`}
      style={styles.chip}
    >
      📄 {citation.source} · p.{citation.page}
    </button>
  );
}

const styles = {
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 12,
    padding: "4px 10px",
    marginRight: 6,
    marginTop: 6,
    borderRadius: 999,
    border: "1px solid #e5e7eb",
    backgroundColor: "#f9fafb",
    color: "#374151",
    cursor: "pointer",
  },
};
