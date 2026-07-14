import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

interface MarkdownContentProps {
  /** Raw markdown or plain text to render. */
  content: string;
  className?: string;
}

/**
 * Renders markdown content as React components via react-markdown.
 *
 * remark-breaks — treats single \\n as <br> (GFM hard-break behaviour),
 * matching the old DIY renderer. Essential for PDF-sourced content where
 * the backend parser joins lines with single newlines.
 *
 * remark-gfm — tables, strikethrough, task lists, fenced code blocks, autolinks.
 * rehype-sanitize — XSS-safe: strips raw HTML from input.
 */
export function MarkdownContent({ content, className }: MarkdownContentProps) {
  return (
    <div className={`markdown-body ${className ?? ""}`}>
      <ReactMarkdown remarkPlugins={[remarkBreaks, remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
