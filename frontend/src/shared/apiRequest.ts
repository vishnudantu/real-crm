import { API_BASE_URL, ApiError } from "../auth/api";
import type { ErrorDetail } from "../auth/api";
import type { StoredSession } from "../auth/session";

export interface BearerRequestOptions {
  getToken: () => StoredSession | null;
  clearToken: () => void;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toDetails(value: unknown): ErrorDetail[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((detail): ErrorDetail[] => {
    if (!isRecord(detail)) return [];
    return [
      {
        ...(typeof detail.field === "string" ? { field: detail.field } : {}),
        ...(typeof detail.message === "string"
          ? { message: detail.message }
          : {}),
        ...(typeof detail.type === "string" ? { type: detail.type } : {}),
      },
    ];
  });
}

function errorMessageFromBody(body: unknown, status: number): string {
  if (isRecord(body)) {
    const envelope = isRecord(body.error) ? body.error : body;
    if (typeof envelope.message === "string") return envelope.message;
    if (typeof envelope.detail === "string") return envelope.detail;
  }
  return status >= 500
    ? "PropFlow is temporarily unavailable. Please try again."
    : "Something went wrong. Please try again.";
}

/**
 * Shared bearer-authenticated fetch wrapper for the admin and operator APIs.
 * Both surfaces share the same JSON error envelope but use separate sessions.
 */
export async function bearerRequest<T>(
  path: string,
  options: BearerRequestOptions,
  init: RequestInit = {},
): Promise<T> {
  const session = options.getToken();
  if (!session?.accessToken) {
    throw new ApiError(401, "UNAUTHORIZED", "Active session required.");
  }

  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Bearer ${session.accessToken}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (error: unknown) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiError(
        0,
        "REQUEST_ABORTED",
        "The request took too long. Please try again.",
      );
    }
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "We couldn't reach PropFlow. Check your connection and try again.",
    );
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (!response.ok) {
    if (response.status === 401) options.clearToken();
    const envelope = isRecord(body) && isRecord(body.error) ? body.error : {};
    const code =
      typeof envelope.code === "string"
        ? envelope.code
        : `HTTP_${response.status}`;
    throw new ApiError(
      response.status,
      code,
      errorMessageFromBody(body, response.status),
      toDetails(envelope.details),
    );
  }

  return body as T;
}

export function errorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError && error.status === 0) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
