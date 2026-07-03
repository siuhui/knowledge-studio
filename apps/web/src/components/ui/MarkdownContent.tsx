import { renderMarkdown } from "@/lib/markdown";

interface MarkdownContentProps {
  /** Raw markdown or plain text to render. HTML is auto-escaped before processing. */
  content: string;
  className?: string;
}

/**
 * Renders markdown content as safe HTML.
 *
 * Uses the project's built-in {@link renderMarkdown} renderer — no external
 * markdown library dependency. XSS-safe: all HTML entities are escaped before
 * markdown processing.
 *
 * Supported syntax: headings (#–####), bold (** or __), italic (* or _).
 */
export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div
      className={className}
      // biome-ignore lint/security/noDangerouslySetInnerHtml: content is sanitized by renderMarkdown
      dangerouslySetInnerHTML={{ __html: renderMarkdown(content) }}
    />
  );
}
