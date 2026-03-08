import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { teacherEntry, type TeacherPublic } from "../api";
import { computeExpiresAt } from "./jwt";
import {
  clearStudentSession,
  clearTeacherSession,
  loadTeacherSession,
  saveTeacherSession,
  TEACHER_SESSION_EVENT,
} from "./storage";

interface TeacherLoginParams {
  email: string;
  password: string;
  name?: string;
  rememberMe: boolean;
}

export interface TeacherAuthContextValue {
  token: string | null;
  expiresAt: number | null;
  teacher: TeacherPublic | null;
  ready: boolean;
  isAuthenticated: boolean;
  loginTeacher: (params: TeacherLoginParams) => Promise<void>;
  logoutTeacher: () => void;
}

const TeacherAuthContext = createContext<TeacherAuthContextValue | undefined>(undefined);

export const TeacherAuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [teacher, setTeacher] = useState<TeacherPublic | null>(null);
  const [ready, setReady] = useState<boolean>(false);

  const logoutTeacher = useCallback(() => {
    clearTeacherSession();
    setToken(null);
    setExpiresAt(null);
    setTeacher(null);
  }, []);

  const restoreTeacherSession = useCallback(() => {
    const restored = loadTeacherSession<TeacherPublic>();
    if (!restored) {
      setToken(null);
      setExpiresAt(null);
      setTeacher(null);
      setReady(true);
      return;
    }
    setToken(restored.token);
    setExpiresAt(restored.expiresAt);
    setTeacher(restored.profile);
    setReady(true);
  }, [logoutTeacher]);

  useEffect(() => {
    restoreTeacherSession();
  }, [restoreTeacherSession]);

  useEffect(() => {
    const syncFromStorage = () => {
      const restored = loadTeacherSession<TeacherPublic>();
      if (!restored) {
        setToken(null);
        setExpiresAt(null);
        setTeacher(null);
        setReady(true);
        return;
      }
      setToken(restored.token);
      setExpiresAt(restored.expiresAt);
      setTeacher(restored.profile);
      setReady(true);
    };
    window.addEventListener(TEACHER_SESSION_EVENT, syncFromStorage as EventListener);
    return () => {
      window.removeEventListener(TEACHER_SESSION_EVENT, syncFromStorage as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!token || !expiresAt) {
      return;
    }
    const remaining = expiresAt - Date.now();
    if (remaining <= 0) {
      logoutTeacher();
      return;
    }
    const timer = window.setTimeout(() => {
      logoutTeacher();
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [token, expiresAt, logoutTeacher]);

  const loginTeacher = useCallback(async (params: TeacherLoginParams) => {
    const response = await teacherEntry(
      params.email.trim(),
      params.password,
      params.name?.trim() || undefined,
    );
    const nextExpiresAt = computeExpiresAt(response.access_token);
    saveTeacherSession<TeacherPublic>({
      token: response.access_token,
      expiresAt: nextExpiresAt,
      profile: response.teacher,
      rememberMe: params.rememberMe,
    });
    // Single-role session policy: teacher login clears any student session.
    clearStudentSession();
    setToken(response.access_token);
    setExpiresAt(nextExpiresAt);
    setTeacher(response.teacher);
  }, []);

  const value = useMemo<TeacherAuthContextValue>(
    () => ({
      token,
      expiresAt,
      teacher,
      ready,
      isAuthenticated: Boolean(token && expiresAt && Date.now() < expiresAt),
      loginTeacher,
      logoutTeacher,
    }),
    [token, expiresAt, teacher, ready, loginTeacher, logoutTeacher],
  );

  return <TeacherAuthContext.Provider value={value}>{children}</TeacherAuthContext.Provider>;
};

export function useTeacherAuth(): TeacherAuthContextValue {
  const context = useContext(TeacherAuthContext);
  if (!context) {
    throw new Error("useTeacherAuth must be used within TeacherAuthProvider");
  }
  return context;
}
