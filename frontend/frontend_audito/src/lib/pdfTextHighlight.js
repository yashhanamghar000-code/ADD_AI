/**
 * REPLACE your existing src/lib/pdfTextHighlight.js with this file.
 *
 * v2 — sliding-window fuzzy word matching instead of raw substring search.
 *
 * Why the old version missed matches: it did an exact substring search
 * after only collapsing whitespace, so ANY difference between the backend
 * snippet and the PDF's extracted text layer (different punctuation
 * spacing, a hyphen pdf.js splits differently, quote-character encoding,
 * a stray table pipe character) caused zero matches. This version:
 *   1. Tokenizes both sides into words, stripping punctuation entirely
 *      (not just whitespace) so "report," and "report" compare equal.
 *   2. Slides a window the length of the snippet across the page's word
 *      list and scores each position by how many words agree — so it
 *      tolerates a few mismatched/missing words (OCR noise, hyphenation)
 *      instead of requiring a perfect match.
 *   3. Picks the best-scoring window above a similarity threshold, and
 *      highlights exactly the text items that window covers.
 */

const MIN_MATCH_SCORE = 0.6; // fraction of words that must agree

function normalizeWord(word) {
  return word.toLowerCase().replace(/[^a-z0-9]/g, "");
}

function tokenize(text) {
  return text.split(/\s+/).map(normalizeWord).filter(Boolean);
}

/**
 * Builds a flat, page-ordered word list from pdf.js text items, where
 * each word remembers which item it came from.
 */
function buildPageWordIndex(textContent) {
  const words = [];
  textContent.items.forEach((item, itemIndex) => {
    const itemWords = tokenize(item.str || "");
    for (const w of itemWords) {
      words.push({ word: w, itemIndex });
    }
  });
  return words;
}

/**
 * Finds the best-matching window of page words for the given snippet.
 * Returns the set of item indices to highlight, or an empty array if no
 * window scores above MIN_MATCH_SCORE.
 */
export function findMatchingItemIndices(textContent, snippet) {
  if (!snippet || !textContent?.items?.length) return [];

  const snippetWords = tokenize(snippet);
  if (snippetWords.length === 0) return [];

  const pageWords = buildPageWordIndex(textContent);
  if (pageWords.length === 0) return [];

  const windowSize = snippetWords.length;
  let bestScore = 0;
  let bestStart = -1;

  const lastStart = Math.max(0, pageWords.length - Math.min(windowSize, pageWords.length));
  for (let start = 0; start <= lastStart; start++) {
    const end = Math.min(start + windowSize, pageWords.length);
    let matches = 0;
    for (let i = start; i < end; i++) {
      const snippetIdx = i - start;
      if (snippetIdx < snippetWords.length && pageWords[i].word === snippetWords[snippetIdx]) {
        matches++;
      }
    }
    const score = matches / windowSize;
    if (score > bestScore) {
      bestScore = score;
      bestStart = start;
    }
    if (score === 1) break; // perfect match, stop early
  }

  if (bestStart === -1 || bestScore < MIN_MATCH_SCORE) {
    return [];
  }

  const end = Math.min(bestStart + windowSize, pageWords.length);
  const itemIndices = new Set();
  for (let i = bestStart; i < end; i++) {
    itemIndices.add(pageWords[i].itemIndex);
  }
  return Array.from(itemIndices).sort((a, b) => a - b);
}

/**
 * Converts matched item indices into absolute-positioned CSS boxes drawn
 * on top of the page's canvas, using the same viewport transform pdf.js
 * used to render that canvas. Adjacent items on the SAME line are merged
 * into one continuous highlight bar instead of one box per word, so the
 * result reads as "this line is highlighted" rather than a row of
 * disconnected chips.
 */
export function computeHighlightRects(textContent, itemIndices, viewport) {
  const boxes = itemIndices
    .map((idx) => textContent.items[idx])
    .filter(Boolean)
    .map((item) => {
      const tx = viewport.transform;
      const m = item.transform;
      const combined = [
        m[0] * tx[0] + m[1] * tx[2],
        m[0] * tx[1] + m[1] * tx[3],
        m[2] * tx[0] + m[3] * tx[2],
        m[2] * tx[1] + m[3] * tx[3],
        m[4] * tx[0] + m[5] * tx[2] + tx[4],
        m[4] * tx[1] + m[5] * tx[3] + tx[5],
      ];
      const fontHeight = Math.hypot(combined[2], combined[3]);
      const width = item.width * Math.hypot(tx[0], tx[1]);
      return {
        left: combined[4],
        top: combined[5] - fontHeight,
        width: Math.max(width, 2),
        height: fontHeight * 1.15,
      };
    });

  if (boxes.length === 0) return [];

  // Merge boxes that sit on (roughly) the same line into single bars —
  // sort by vertical position, group by overlapping top/height, then
  // union each group's horizontal extent.
  boxes.sort((a, b) => a.top - b.top || a.left - b.left);

  const lineGroups = [];
  const LINE_TOLERANCE = 4; // px

  for (const box of boxes) {
    const lastGroup = lineGroups[lineGroups.length - 1];
    if (lastGroup && Math.abs(lastGroup.top - box.top) <= LINE_TOLERANCE) {
      lastGroup.left = Math.min(lastGroup.left, box.left);
      lastGroup.right = Math.max(lastGroup.right, box.left + box.width);
      lastGroup.bottom = Math.max(lastGroup.bottom, box.top + box.height);
      lastGroup.top = Math.min(lastGroup.top, box.top);
    } else {
      lineGroups.push({
        top: box.top,
        left: box.left,
        right: box.left + box.width,
        bottom: box.top + box.height,
      });
    }
  }

  return lineGroups.map((g) => ({
    left: g.left,
    top: g.top,
    width: g.right - g.left,
    height: g.bottom - g.top,
  }));
}
