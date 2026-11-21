import type { StoredSession } from "../auth/session";

const ACCESS_TOKEN_KEY = "propflow.operator.access-token";
const EXPIRES_AT_KEY = "propflow.operator.access-token-expires-at";

function storageOrNull(): Storage | null {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
}

/** Operator tokens are kept separate from tenant tokens and never persisted. */
export function saveOperatorSession(
  accessToken: string,
  expiresInSeconds: number,
): void {
  const storage = storageOrNull();
  if (!storage) return;

  const expiresAt = Date.now() + Math.max(0, expiresInSeconds) * 1000;
  try {
    storage.setItem(ACCESS_TOKEN_KEY, accessToken);
    storage.setItem(EXPIRES_AT_KEY, String(expiresAt));
  } catch {
    // Storage can be unavailable in restricted browsing modes.
  }
}

export function getOperatorSession(): StoredSession | null {
  const storage = storageOrNull();
  if (!storage) return null;

  try {
    const accessToken = storage.getItem(ACCESS_TOKEN_KEY);
    const expiresAt = Number(storage.getItem(EXPIRES_AT_KEY));

    if (!accessToken || !Number.isFinite(expiresAt) || expiresAt <= Date.now()) {
      clearOperatorSession();
      return null;
    }

    return { accessToken, expiresAt };
  } catch {
    clearOperatorSession();
    return null;
  }
}

export function clearOperatorSession(): void {
  const storage = storageOrNull();
  if (!storage) return;

  try {
    storage.removeItem(ACCESS_TOKEN_KEY);
    storage.removeItem(EXPIRES_AT_KEY);
  } catch {
    // Nothing else to do when storage is unavailable.
  }
}
