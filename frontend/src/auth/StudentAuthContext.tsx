import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { studentEntry, studentLogin, type StudentPublic } from "../api";
import { computeExpiresAt } from "./jwt";
import {
  clearStudentSession,
  clearTeacherSession,
  loadStudentSession,
  saveStudentSession,
  STUDENT_SESSION_EVENT,
} from "./storage";

interface StudentLoginParams {
  email: string;
  password: string;
  name?: string;
  assignmentId?: number;
  rememberMe: boolean;
}

export interface StudentAuthContextValue {
  token: string | null;
  expiresAt: number | null;
  student: StudentPublic | null;
  ready: boolean;
  isAuthenticated: boolean;
  loginStudent: (params: StudentLoginParams) => Promise<void>;
  logoutStudent: () => void;
}

const StudentAuthContext = createContext<StudentAuthContextValue | undefined>(undefined);

export const StudentAuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<number | null>(null);
  const [student, setStudent] = useState<StudentPublic | null>(null);
  const [ready, setReady] = useState<boolean>(false);

  const logoutStudent = useCallback(() => {
    clearStudentSession();
    setToken(null);
    setExpiresAt(null);
    setStudent(null);
  }, []);

  const restoreStudentSession = useCallback(() => {
    const restored = loadStudentSession<StudentPublic>();
    if (!restored) {
      setToken(null);
      setExpiresAt(null);
      setStudent(null);
      setReady(true);
      return;
    }
    setToken(restored.token);
    setExpiresAt(restored.expiresAt);
    setStudent(restored.profile);
    setReady(true);
  }, [logoutStudent]);

  useEffect(() => {
    restoreStudentSession();
  }, [restoreStudentSession]);

  useEffect(() => {
    const syncFromStorage = () => {
      const restored = loadStudentSession<StudentPublic>();
      if (!restored) {
        setToken(null);
        setExpiresAt(null);
        setStudent(null);
        setReady(true);
        return;
      }
      setToken(restored.token);
      setExpiresAt(restored.expiresAt);
      setStudent(restored.profile);
      setReady(true);
    };
    window.addEventListener(STUDENT_SESSION_EVENT, syncFromStorage as EventListener);
    return () => {
      window.removeEventListener(STUDENT_SESSION_EVENT, syncFromStorage as EventListener);
    };
  }, []);

  useEffect(() => {
    if (!token || !expiresAt) {
      return;
    }
    const remaining = expiresAt - Date.now();
    if (remaining <= 0) {
      logoutStudent();
      return;
    }
    const timer = window.setTimeout(() => {
      logoutStudent();
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [token, expiresAt, logoutStudent]);

  const loginStudent = useCallback(async (params: StudentLoginParams) => {
    const email = params.email.trim();
    const response =
      params.assignmentId !== undefined
        ? await studentEntry(email, params.password, {
            name: params.name?.trim() || undefined,
            assignment_id: params.assignmentId,
          })
        : await studentLogin(email, params.password);

    const nextExpiresAt = computeExpiresAt(response.access_token);
    saveStudentSession<StudentPublic>({
      token: response.access_token,
      expiresAt: nextExpiresAt,
      profile: response.student,
      rememberMe: params.rememberMe,
    });
    // Single-role session policy: student login clears any teacher session.
    clearTeacherSession();
    setToken(response.access_token);
    setExpiresAt(nextExpiresAt);
    setStudent(response.student);
  }, []);

  const value = useMemo<StudentAuthContextValue>(
    () => ({
      token,
      expiresAt,
      student,
      ready,
      isAuthenticated: Boolean(token && expiresAt && Date.now() < expiresAt),
      loginStudent,
      logoutStudent,
    }),
    [token, expiresAt, student, ready, loginStudent, logoutStudent],
  );

  return <StudentAuthContext.Provider value={value}>{children}</StudentAuthContext.Provider>;
};

export function useStudentAuth(): StudentAuthContextValue {
  const context = useContext(StudentAuthContext);
  if (!context) {
    throw new Error("useStudentAuth must be used within StudentAuthProvider");
  }
  return context;
}
