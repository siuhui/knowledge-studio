import type { StreamEvent } from "./types";

/**
 * Parse an SSE (Server-Sent Events) stream from a fetch Response body.
 *
 * Calls ``onEvent`` for each parsed JSON event.  Handles partial chunks
 * by buffering incomplete lines between reads.  Stops when the stream
 * ends, ``signal`` is aborted, or ``onEvent`` throws.
 */
export async function parseSSEStream(
  stream: ReadableStream<Uint8Array>,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) break;
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      // Last element may be incomplete — keep it in buffer
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const payload = line.slice(6).trim();
          if (!payload) continue;
          try {
            onEvent(JSON.parse(payload) as StreamEvent);
          } catch {
            // Skip malformed events — the SSE spec says clients SHOULD
            // ignore lines they don't understand
          }
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
