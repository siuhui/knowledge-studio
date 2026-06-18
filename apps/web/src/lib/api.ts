import { ApiError } from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("kb_access_token");
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export async function api<T>(
  path: string,
  options?: RequestInit,
): Promise<{ data: T; requestId: string }> {
  const requestId = crypto.randomUUID();
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      "X-Request-ID": requestId,
      ...getAuthHeader(),
      ...options?.headers,
    },
    ...options,
  });
  const rid = res.headers.get("X-Request-ID") || requestId;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ code: "NETWORK_ERROR", message: res.statusText }));
    throw new ApiError(err.code, err.message, res.status, rid);
  }
  return { data: (await res.json()).data as T, requestId: rid };
}

export async function uploadFile(
  path: string,
  file: File,
  extraFields: Record<string, string>,
): Promise<{ data: unknown; requestId: string }> {
  const requestId = crypto.randomUUID();
  const formData = new FormData();
  formData.append("file", file);
  for (const [key, value] of Object.entries(extraFields)) {
    formData.append(key, value);
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "X-Request-ID": requestId,
      ...(typeof window !== "undefined"
        ? (() => {
            const token = localStorage.getItem("kb_access_token");
            return token ? { Authorization: `Bearer ${token}` } : {};
          })()
        : {}),
    },
    body: formData,
  });

  const rid = res.headers.get("X-Request-ID") || requestId;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ code: "NETWORK_ERROR", message: res.statusText }));
    throw new ApiError(err.code, err.message, res.status, rid);
  }
  return { data: (await res.json()).data as unknown, requestId: rid };
}
