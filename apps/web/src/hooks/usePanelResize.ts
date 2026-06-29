"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Custom hook for drag-to-resize panel functionality.
 *
 * Returns the current panel width, whether a drag is in progress,
 * and props to spread onto the drag handle element.
 *
 * During drag:
 * - Sets body cursor to col-resize and disables text selection globally
 * - Clamps width between minWidth (300px) and maxWidth (viewport minus 360px chat + sidebar, capped at 65vw)
 *
 * @param initialWidth - Starting panel width in pixels (default 400)
 */
export function usePanelResize(initialWidth = 400) {
  const [width, setWidth] = useState(initialWidth);
  const [isDragging, setIsDragging] = useState(false);

  // Refs to track drag start position so we don't depend on stale state
  const startXRef = useRef(0);
  const startWidthRef = useRef(initialWidth);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      // Only respond to primary (left) mouse button
      if (e.button !== 0) return;

      setIsDragging(true);
      startXRef.current = e.clientX;
      startWidthRef.current = width;
      e.preventDefault();
    },
    [width],
  );

  // Attach document-level listeners while dragging
  useEffect(() => {
    if (!isDragging) return;

    const prevUserSelect = document.body.style.userSelect;
    const prevCursor = document.body.style.cursor;

    // Global drag overlay: prevent text selection and set consistent cursor
    document.body.style.userSelect = "none";
    document.body.style.cursor = "col-resize";

    const handleMouseMove = (e: MouseEvent) => {
      // Calculate delta: dragging left shrinks the panel (positive delta → smaller panel)
      const delta = startXRef.current - e.clientX;
      const viewportWidth = window.innerWidth;
      // Right panel can take at most 65vw, but must leave at least 360px for the chat area
      const maxWidthByViewport = Math.floor(viewportWidth * 0.65);
      // The approx space available: viewport - 360 (chat min) - 260 (sidebar min) - 6 (drag handle)
      const maxWidthByChatGuard = viewportWidth - 360 - 260 - 6;
      const maxWidth = Math.min(maxWidthByViewport, Math.max(maxWidthByChatGuard, 300));

      const newWidth = Math.max(300, Math.min(maxWidth, startWidthRef.current + delta));
      setWidth(newWidth);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);

      // Restore body styles on cleanup
      document.body.style.userSelect = prevUserSelect;
      document.body.style.cursor = prevCursor;
    };
  }, [isDragging]);

  const dragHandleProps = {
    onMouseDown: handleMouseDown,
    role: "separator" as const,
    "aria-orientation": "vertical" as const,
    "aria-label": "Resize panel",
  };

  return { width, isDragging, dragHandleProps };
}
