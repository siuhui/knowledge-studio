/**
 * Lightweight markdown-to-HTML renderer for document content.
 *
 * Processing order (XSS-safe):
 * 1. Escape all HTML special characters to prevent injection
 * 2. Process block-level elements (headings) — these produce block tags that
 *    naturally break the flow
 * 3. Process inline formatting (bold, italic)
 *
 * Block elements are wrapped in a `<div>` to ensure they display as blocks
 * and do not merge into adjacent paragraph text.
 *
 * Supported syntax:
 * - ## text  → <h4>text</h4> (block)
 * - # text   → <h3>text</h3> (block)
 * - **text** → <strong>text</strong> (inline)
 * - *text*   → <em>text</em> (inline)
 * - __text__ → <strong>text</strong> (inline)
 */

/**
 * Render a markdown string to safe HTML.
 * HTML entities in the input are escaped before any markdown processing.
 */
export function renderMarkdown(text: string): string {
  // Step 1: Escape HTML to prevent XSS
  const safeText = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

  // Step 2: Process block-level elements first (headings), then join with <br> to preserve
  // line breaks in HTML (newlines collapse to whitespace without explicit <br> tags).
  // Headings are already block-level tags so they naturally separate from adjacent text.
  const html = safeText
    .split("\n")
    .map((line) => {
      let trimmed = line;

      // #### heading → <h5>
      if (/^####\s+\S/.test(trimmed)) {
        return `<h5>${trimmed.replace(/^####\s+/, "")}</h5>`;
      }
      // ### heading → <h4>
      if (/^###\s+\S/.test(trimmed)) {
        return `<h4>${trimmed.replace(/^###\s+/, "")}</h4>`;
      }
      // ## heading → <h3>
      if (/^##\s+\S/.test(trimmed)) {
        return `<h3>${trimmed.replace(/^##\s+/, "")}</h3>`;
      }
      // # heading → <h2>
      if (/^#\s+\S/.test(trimmed)) {
        return `<h2>${trimmed.replace(/^#\s+/, "")}</h2>`;
      }

      // Step 3: Process inline formatting on the line
      // Bold: **text** — strip the asterisks, wrap in <strong>
      trimmed = trimmed.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      trimmed = trimmed.replace(/__(.+?)__/g, "<strong>$1</strong>");

      // Italic: *text* (not **), _text_ (not __)
      trimmed = trimmed.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");
      trimmed = trimmed.replace(/(?<!_)_(?!_)(.+?)(?<!_)_(?!_)/g, "<em>$1</em>");

      return trimmed;
    })
    .join("<br>");

  return html;
}
