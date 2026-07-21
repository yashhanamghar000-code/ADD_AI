/**
 * NEW FILE — copy into src/lib/pdfTextHighlight.js
 *
 * Pure helper functions: given a rendered PDF.js page's text content and
 * a target snippet, find which text items on the page contain that
 * snippet and compute where to draw highlight boxes over the canvas.
 *
 * This does word/item-level highlighting (not exact character ranges) —
 * good enough to visually point at "this is the sentence the answer came
 * from" without needing a full text-diffing layer.
 */

function normalize(str) {
  return str.replace(/\s+/g, " ").trim().toLowerCase();
}

/**
 * Finds the contiguous run of text items whose concatenated text contains
 * the snippet, and returns their indices into `textContent.items`.
 */
export function findMatchingItemIndices(textContent, snippet) {
  if (!snippet || !textContent?.items?.length) return [];

  const items = textContent.items;
  const normalizedSnippet = normalize(snippet);
  if (!normalizedSnippet) return [];

  // Build a flat string + a parallel map of (charIndex -> itemIndex).
  let flat = "";
  const charToItem = [];
  items.forEach((item, itemIdx) => {
    const text = item.str || "";
    for (let i = 0; i < text.length; i++) {
      charToItem.push(itemIdx);
    }
    flat += text;
    // pdf.js marks a line/word break with hasEOL or trailing space in most
    // extracted content; add a space between items so words don't fuse.
    flat += " ";
    charToItem.push(itemIdx);
  });

  const normalizedFlat = normalize(flat);

  // normalize() collapses whitespace, so char offsets in normalizedFlat
  // don't line up 1:1 with `flat`/`charToItem` anymore. Do a simpler,
  // more robust pass instead: try shrinking the snippet from the back
  // until we find a substring match — snippets can legitimately not
  // appear verbatim (OCR noise, hyphenation) so we degrade gracefully.
  let matchIndex = normalizedFlat.indexOf(normalizedSnippet);
  let words = normalizedSnippet.split(" ");
  while (matchIndex === -1 && words.length > 3) {
    words = words.slice(0, -1);
    matchIndex = normalizedFlat.indexOf(words.join(" "));
  }
  if (matchIndex === -1) return [];

  // Map the matched normalized-text range back to items by scanning the
  // ORIGINAL (non-normalized) flat string for the same words, item by
  // item, since normalization only removed whitespace duplication.
  const matchWords = words;
  const matchedIndices = new Set();
  let searchStart = 0;

  for (const word of matchWords) {
    if (!word) continue;
    const idx = flat.toLowerCase().indexOf(word, searchStart);
    if (idx === -1) continue;
    for (let i = idx; i < idx + word.length && i < charToItem.length; i++) {
      matchedIndices.add(charToItem[i]);
    }
    searchStart = idx + word.length;
  }

  return Array.from(matchedIndices).sort((a, b) => a - b);
}

/**
 * Converts matched item indices into absolute-positioned CSS boxes drawn
 * on top of the page's canvas, using the same viewport transform pdf.js
 * used to render that canvas.
 */
export function computeHighlightRects(textContent, itemIndices, viewport) {
  const rects = [];
  for (const idx of itemIndices) {
    const item = textContent.items[idx];
    if (!item) continue;

    const tx = viewport.transform;
    const m = item.transform;
    // Combine the item's text-space transform with the page viewport
    // transform (standard pdf.js text-layer positioning approach).
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

    rects.push({
      left: combined[4],
      top: combined[5] - fontHeight,
      width: Math.max(width, 2),
      height: fontHeight * 1.15,
    });
  }
  return rects;
}
