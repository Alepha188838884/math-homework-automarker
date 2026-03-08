export type PersistMode = "local" | "session";

export interface SessionPayload<TProfile> {
  token: string;
  expiresAt: number;
  profile: TProfile | null;
  rememberMe: boolean;
}

export interface StoredSession<TProfile> {
  token: string;
  expiresAt: number;
  profile: TProfile | null;
  persist: PersistMode;
}

const TEACHER_ACCESS_TOKEN_KEY = "teacher_access_token";
const TEACHER_EXPIRES_AT_KEY = "teacher_expires_at";
const TEACHER_PROFILE_KEY = "teacher_profile";
const TEACHER_PERSIST_KEY = "teacher_persist";

const STUDENT_ACCESS_TOKEN_KEY = "student_access_token";
const STUDENT_EXPIRES_AT_KEY = "student_expires_at";
const STUDENT_PROFILE_KEY = "student_profile";
const STUDENT_PERSIST_KEY = "student_persist";

export const TEACHER_SESSION_EVENT = "mathhw:teacher-session-changed";
export const STUDENT_SESSION_EVENT = "mathhw:student-session-changed";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function getStorage(mode: PersistMode): Storage | null {
  if (!isBrowser()) {
    return null;
  }
  try {
    return mode === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

function parseNumber(value: string | null): number | null {
  if (!value) {
    return null;
  }
  const n = Number(value);
  if (!Number.isFinite(n)) {
    return null;
  }
  return n;
}

function parseProfile<TProfile>(raw: string | null): TProfile | null {
  if (!raw) {
    return null;
  }
  try {
    return JSON.parse(raw) as TProfile;
  } catch {
    return null;
  }
}

export function isExpired(expiresAt: number | null): boolean {
  if (!expiresAt || !Number.isFinite(expiresAt)) {
    return true;
  }
  return Date.now() >= expiresAt;
}

function clearByKeys(keys: readonly string[]): void {
  for (const mode of ["local", "session"] as const) {
    const storage = getStorage(mode);
    if (!storage) {
      continue;
    }
    for (const key of keys) {
      storage.removeItem(key);
    }
  }
}

function emitSessionEvent(eventName: string): void {
  if (!isBrowser()) {
    return;
  }
  window.dispatchEvent(new CustomEvent(eventName));
}

function saveSession<TProfile>(
  keys: {
    accessToken: string;
    expiresAt: string;
    profile: string;
    persist: string;
  },
  payload: SessionPayload<TProfile>,
): void {
  clearByKeys([keys.accessToken, keys.expiresAt, keys.profile, keys.persist]);
  const mode: PersistMode = payload.rememberMe ? "local" : "session";
  const storage = getStorage(mode);
  if (!storage) {
    return;
  }
  storage.setItem(keys.accessToken, payload.token);
  storage.setItem(keys.expiresAt, String(payload.expiresAt));
  storage.setItem(keys.persist, mode);
  if (payload.profile !== null) {
    storage.setItem(keys.profile, JSON.stringify(payload.profile));
  }
}

function loadSession<TProfile>(
  keys: {
    accessToken: string;
    expiresAt: string;
    profile: string;
    persist: string;
  },
): StoredSession<TProfile> | null {
  for (const mode of ["session", "local"] as const) {
    const storage = getStorage(mode);
    if (!storage) {
      continue;
    }
    const token = storage.getItem(keys.accessToken);
    if (!token) {
      continue;
    }
    const expiresAt = parseNumber(storage.getItem(keys.expiresAt));
    if (isExpired(expiresAt)) {
      clearByKeys([keys.accessToken, keys.expiresAt, keys.profile, keys.persist]);
      return null;
    }
    const profile = parseProfile<TProfile>(storage.getItem(keys.profile));
    return {
      token,
      expiresAt: expiresAt as number,
      profile,
      persist: mode,
    };
  }
  return null;
}

function saveProfileOnly<TProfile>(
  keys: {
    accessToken: string;
    expiresAt: string;
    profile: string;
  },
  profile: TProfile,
): void {
  for (const mode of ["session", "local"] as const) {
    const storage = getStorage(mode);
    if (!storage) {
      continue;
    }
    if (storage.getItem(keys.accessToken) && storage.getItem(keys.expiresAt)) {
      storage.setItem(keys.profile, JSON.stringify(profile));
      return;
    }
  }
}

export function saveTeacherSession<TProfile>(payload: SessionPayload<TProfile>): void {
  saveSession(
    {
      accessToken: TEACHER_ACCESS_TOKEN_KEY,
      expiresAt: TEACHER_EXPIRES_AT_KEY,
      profile: TEACHER_PROFILE_KEY,
      persist: TEACHER_PERSIST_KEY,
    },
    payload,
  );
  emitSessionEvent(TEACHER_SESSION_EVENT);
}

export function saveStudentSession<TProfile>(payload: SessionPayload<TProfile>): void {
  saveSession(
    {
      accessToken: STUDENT_ACCESS_TOKEN_KEY,
      expiresAt: STUDENT_EXPIRES_AT_KEY,
      profile: STUDENT_PROFILE_KEY,
      persist: STUDENT_PERSIST_KEY,
    },
    payload,
  );
  emitSessionEvent(STUDENT_SESSION_EVENT);
}

export function loadTeacherSession<TProfile>(): StoredSession<TProfile> | null {
  return loadSession<TProfile>({
    accessToken: TEACHER_ACCESS_TOKEN_KEY,
    expiresAt: TEACHER_EXPIRES_AT_KEY,
    profile: TEACHER_PROFILE_KEY,
    persist: TEACHER_PERSIST_KEY,
  });
}

export function loadStudentSession<TProfile>(): StoredSession<TProfile> | null {
  return loadSession<TProfile>({
    accessToken: STUDENT_ACCESS_TOKEN_KEY,
    expiresAt: STUDENT_EXPIRES_AT_KEY,
    profile: STUDENT_PROFILE_KEY,
    persist: STUDENT_PERSIST_KEY,
  });
}

export function clearTeacherSession(): void {
  clearByKeys([
    TEACHER_ACCESS_TOKEN_KEY,
    TEACHER_EXPIRES_AT_KEY,
    TEACHER_PROFILE_KEY,
    TEACHER_PERSIST_KEY,
  ]);
  emitSessionEvent(TEACHER_SESSION_EVENT);
}

export function clearStudentSession(): void {
  clearByKeys([
    STUDENT_ACCESS_TOKEN_KEY,
    STUDENT_EXPIRES_AT_KEY,
    STUDENT_PROFILE_KEY,
    STUDENT_PERSIST_KEY,
  ]);
  emitSessionEvent(STUDENT_SESSION_EVENT);
}

export function setTeacherProfileInStorage<TProfile>(profile: TProfile): void {
  saveProfileOnly(
    {
      accessToken: TEACHER_ACCESS_TOKEN_KEY,
      expiresAt: TEACHER_EXPIRES_AT_KEY,
      profile: TEACHER_PROFILE_KEY,
    },
    profile,
  );
  emitSessionEvent(TEACHER_SESSION_EVENT);
}

export function setStudentProfileInStorage<TProfile>(profile: TProfile): void {
  saveProfileOnly(
    {
      accessToken: STUDENT_ACCESS_TOKEN_KEY,
      expiresAt: STUDENT_EXPIRES_AT_KEY,
      profile: STUDENT_PROFILE_KEY,
    },
    profile,
  );
  emitSessionEvent(STUDENT_SESSION_EVENT);
}
