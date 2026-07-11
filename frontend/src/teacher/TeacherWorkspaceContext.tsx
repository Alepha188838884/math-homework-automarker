import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  type AnswerFileResponse,
  type Assignment,
  type Course,
  type GradeAllSummary,
  type GradeResult,
  type StudentAssignmentStatus,
  type StudentPublic,
  type Submission,
  fetchAssignmentsForCourse,
  fetchCourseStudents,
  fetchMyCourses,
  fetchSubmissionResult,
  fetchSubmissionsForAssignment,
  fetchStudentsStatusForAssignment,
  gradeAllSubmissions,
  gradeSubmission,
  setBaseUrl,
  uploadSolution,
} from "../api";
import { getErrorMessage, type StatusMessage } from "../utils";


const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const BACKEND_BASE_URL_KEY = "teacher_backend_base_url";
const SELECTED_COURSE_ID_KEY = "teacher_selected_course_id";
const SELECTED_ASSIGNMENT_ID_KEY = "teacher_selected_assignment_id";

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

function normalizeBaseUrlInput(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function readStoredString(key: string, fallback: string): string {
  if (!isBrowser()) {
    return fallback;
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return fallback;
    }
    const normalized = raw.trim();
    return normalized || fallback;
  } catch {
    return fallback;
  }
}

function readStoredNumber(key: string): number | null {
  if (!isBrowser()) {
    return null;
  }
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) {
      return null;
    }
    const value = Number(raw);
    return Number.isFinite(value) && value > 0 ? value : null;
  } catch {
    return null;
  }
}

function writeStoredString(key: string, value: string): void {
  if (!isBrowser()) {
    return;
  }
  try {
    window.localStorage.setItem(key, value);
  } catch {
  }
}

function writeStoredNumber(key: string, value: number | null): void {
  if (!isBrowser()) {
    return;
  }
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
      return;
    }
    window.localStorage.setItem(key, String(value));
  } catch {
  }
}

export interface TeacherWorkspaceContextValue {
  backendBaseUrl: string;
  courses: Course[];
  selectedCourseId: number | null;
  selectedAssignmentId: number | null;
  courseStudents: StudentPublic[];
  courseAssignments: Assignment[];
  submissions: Submission[];
  studentsStatus: StudentAssignmentStatus[];
  latestSolution: AnswerFileResponse | null;
  gradeAllSummary: GradeAllSummary | null;
  modalResult: GradeResult | null;
  isModalOpen: boolean;
  gradingIds: Set<number>;
  viewingIds: Set<number>;
  solutionMessage: StatusMessage | null;
  actionMessage: StatusMessage | null;
  coursesError: string | null;
  assignmentsError: string | null;
  courseStudentsError: string | null;
  submissionDataError: string | null;
  isLoadingCourses: boolean;
  isLoadingAssignments: boolean;
  isLoadingCourseStudents: boolean;
  isLoadingSubmissionData: boolean;
  isUploadingSolution: boolean;
  isGradingAll: boolean;
  setSelectedCourseId: (courseId: number | null) => void;
  setSelectedAssignmentId: (assignmentId: number | null) => void;
  loadCourses: () => Promise<void>;
  loadAssignmentsForCourse: (courseId: number) => Promise<void>;
  loadCourseStudents: (courseId: number) => Promise<void>;
  loadAssignmentData: (assignmentId: number) => Promise<void>;
  applyBackendBaseUrl: (nextBaseUrl: string) => Promise<void>;
  uploadSolutionFile: (file: File) => Promise<AnswerFileResponse>;
  gradeAllSelectedAssignment: () => Promise<GradeAllSummary | null>;
  gradeSubmissionById: (submissionId: number) => Promise<void>;
  viewSubmissionResult: (submissionId: number) => Promise<void>;
  closeResultModal: () => void;
}

const TeacherWorkspaceContext = createContext<TeacherWorkspaceContextValue | undefined>(undefined);

export const TeacherWorkspaceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [backendBaseUrl, setBackendBaseUrlState] = useState<string>(() =>
    readStoredString(BACKEND_BASE_URL_KEY, defaultBaseUrl),
  );

  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseIdState, setSelectedCourseIdState] = useState<number | null>(() =>
    readStoredNumber(SELECTED_COURSE_ID_KEY),
  );
  const [courseStudents, setCourseStudents] = useState<StudentPublic[]>([]);

  const [courseAssignments, setCourseAssignments] = useState<Assignment[]>([]);
  const [selectedAssignmentIdState, setSelectedAssignmentIdState] = useState<number | null>(() =>
    readStoredNumber(SELECTED_ASSIGNMENT_ID_KEY),
  );

  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [studentsStatus, setStudentsStatus] = useState<StudentAssignmentStatus[]>([]);

  const [latestSolution, setLatestSolution] = useState<AnswerFileResponse | null>(null);
  const [gradeAllSummary, setGradeAllSummary] = useState<GradeAllSummary | null>(null);
  const [modalResult, setModalResult] = useState<GradeResult | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);
  const [gradingIds, setGradingIds] = useState<Set<number>>(new Set());
  const [viewingIds, setViewingIds] = useState<Set<number>>(new Set());

  const [solutionMessage, setSolutionMessage] = useState<StatusMessage | null>(null);
  const [actionMessage, setActionMessage] = useState<StatusMessage | null>(null);

  const [coursesError, setCoursesError] = useState<string | null>(null);
  const [assignmentsError, setAssignmentsError] = useState<string | null>(null);
  const [courseStudentsError, setCourseStudentsError] = useState<string | null>(null);
  const [submissionDataError, setSubmissionDataError] = useState<string | null>(null);

  const [isLoadingCourses, setIsLoadingCourses] = useState<boolean>(false);
  const [isLoadingAssignments, setIsLoadingAssignments] = useState<boolean>(false);
  const [isLoadingCourseStudents, setIsLoadingCourseStudents] = useState<boolean>(false);
  const [isLoadingSubmissionData, setIsLoadingSubmissionData] = useState<boolean>(false);
  const [isUploadingSolution, setIsUploadingSolution] = useState<boolean>(false);
  const [isGradingAll, setIsGradingAll] = useState<boolean>(false);

  const clearGradingState = useCallback(() => {
    setLatestSolution(null);
    setGradeAllSummary(null);
    setModalResult(null);
    setIsModalOpen(false);
    setGradingIds(new Set());
    setViewingIds(new Set());
    setSolutionMessage(null);
    setActionMessage(null);
  }, []);

  const loadCourses = useCallback(async () => {
    setIsLoadingCourses(true);
    setCoursesError(null);
    try {
      const data = await fetchMyCourses();
      setCourses(data);
      setSelectedCourseIdState((prev) => {
        if (prev !== null && data.some((item) => item.id === prev)) {
          return prev;
        }
        return data.length > 0 ? data[0].id : null;
      });
    } catch (error) {
      setCoursesError(getErrorMessage(error));
    } finally {
      setIsLoadingCourses(false);
    }
  }, []);

  const loadAssignmentsForCourse = useCallback(async (courseId: number) => {
    setIsLoadingAssignments(true);
    setAssignmentsError(null);
    try {
      const data = await fetchAssignmentsForCourse(courseId);
      setCourseAssignments(data);
      setSelectedAssignmentIdState((prev) => {
        if (prev !== null && data.some((item) => item.id === prev)) {
          return prev;
        }
        return data.length > 0 ? data[0].id : null;
      });
    } catch (error) {
      setAssignmentsError(getErrorMessage(error));
    } finally {
      setIsLoadingAssignments(false);
    }
  }, []);

  const loadCourseStudents = useCallback(async (courseId: number) => {
    setIsLoadingCourseStudents(true);
    setCourseStudentsError(null);
    try {
      const data = await fetchCourseStudents(courseId);
      setCourseStudents(data);
    } catch (error) {
      setCourseStudentsError(getErrorMessage(error));
    } finally {
      setIsLoadingCourseStudents(false);
    }
  }, []);

  const loadAssignmentData = useCallback(async (assignmentId: number) => {
    setIsLoadingSubmissionData(true);
    setSubmissionDataError(null);
    try {
      const [submissionData, statusData] = await Promise.all([
        fetchSubmissionsForAssignment(assignmentId),
        fetchStudentsStatusForAssignment(assignmentId),
      ]);
      setSubmissions(submissionData);
      setStudentsStatus(statusData);
    } catch (error) {
      setSubmissionDataError(getErrorMessage(error));
    } finally {
      setIsLoadingSubmissionData(false);
    }
  }, []);

  const applyBackendBaseUrl = useCallback(
    async (nextBaseUrl: string) => {
      const normalized = normalizeBaseUrlInput(nextBaseUrl);
      setBaseUrl(normalized);
      setBackendBaseUrlState(normalized);
      writeStoredString(BACKEND_BASE_URL_KEY, normalized);
      await loadCourses();
    },
    [loadCourses],
  );

  const uploadSolutionFile = useCallback(
    async (file: File) => {
      if (selectedAssignmentIdState === null) {
        throw new Error("请先选择作业。");
      }
      setSolutionMessage(null);
      setIsUploadingSolution(true);
      try {
        const response = await uploadSolution(selectedAssignmentIdState, file);
        setLatestSolution(response);
        setSolutionMessage({
          type: "success",
          text: `官方答案上传成功：${response.original_filename}`,
        });
        return response;
      } catch (error) {
        const message = getErrorMessage(error);
        setSolutionMessage({ type: "error", text: message });
        throw error;
      } finally {
        setIsUploadingSolution(false);
      }
    },
    [selectedAssignmentIdState],
  );

  const gradeSubmissionById = useCallback(
    async (submissionId: number) => {
      setActionMessage(null);
      setGradingIds((prev) => new Set(prev).add(submissionId));
      try {
        const result = await gradeSubmission(submissionId);
        setActionMessage({
          type: "success",
          text:
            result.status === "needs_manual_review"
              ? `Submission ${submissionId} 自动评分完成：${result.total_score}/${result.max_total_score}，仍需人工复核`
              : `Submission ${submissionId} 批改完成：${result.total_score}/${result.max_total_score}`,
        });
      } catch (error) {
        setActionMessage({ type: "error", text: getErrorMessage(error) });
      } finally {
        setGradingIds((prev) => {
          const next = new Set(prev);
          next.delete(submissionId);
          return next;
        });
        if (selectedAssignmentIdState !== null) {
          await loadAssignmentData(selectedAssignmentIdState);
        }
      }
    },
    [loadAssignmentData, selectedAssignmentIdState],
  );

  const viewSubmissionResult = useCallback(async (submissionId: number) => {
    setActionMessage(null);
    setViewingIds((prev) => new Set(prev).add(submissionId));
    try {
      const result = await fetchSubmissionResult(submissionId);
      setModalResult(result);
      setIsModalOpen(true);
    } catch (error) {
      const message = getErrorMessage(error);
      setActionMessage({
        type: "error",
        text: message.includes("HTTP 404") ? "该提交暂无批改结果。" : message,
      });
    } finally {
      setViewingIds((prev) => {
        const next = new Set(prev);
        next.delete(submissionId);
        return next;
      });
    }
  }, []);

  const gradeAllSelectedAssignment = useCallback(async () => {
    if (selectedAssignmentIdState === null) {
      throw new Error("请先选择作业。");
    }
    setActionMessage(null);
    setGradeAllSummary(null);
    setIsGradingAll(true);
    try {
      const summary = await gradeAllSubmissions(selectedAssignmentIdState);
      setGradeAllSummary(summary);
      setActionMessage({
        type: "success",
        text: `批量批改完成：graded=${summary.graded}, failed=${summary.failed}`,
      });
      await loadAssignmentData(selectedAssignmentIdState);
      return summary;
    } catch (error) {
      setActionMessage({ type: "error", text: getErrorMessage(error) });
      return null;
    } finally {
      setIsGradingAll(false);
    }
  }, [loadAssignmentData, selectedAssignmentIdState]);

  const closeResultModal = useCallback(() => {
    setIsModalOpen(false);
  }, []);

  const setSelectedCourseId = useCallback((courseId: number | null) => {
    setSelectedCourseIdState(courseId);
  }, []);

  const setSelectedAssignmentId = useCallback((assignmentId: number | null) => {
    setSelectedAssignmentIdState(assignmentId);
  }, []);

  useEffect(() => {
    const normalized = normalizeBaseUrlInput(backendBaseUrl);
    try {
      setBaseUrl(normalized);
    } catch {
      setBaseUrl(defaultBaseUrl);
      setBackendBaseUrlState(defaultBaseUrl);
      writeStoredString(BACKEND_BASE_URL_KEY, defaultBaseUrl);
    }
    void loadCourses();
  }, []);

  useEffect(() => {
    writeStoredString(BACKEND_BASE_URL_KEY, backendBaseUrl);
  }, [backendBaseUrl]);

  useEffect(() => {
    writeStoredNumber(SELECTED_COURSE_ID_KEY, selectedCourseIdState);
  }, [selectedCourseIdState]);

  useEffect(() => {
    writeStoredNumber(SELECTED_ASSIGNMENT_ID_KEY, selectedAssignmentIdState);
  }, [selectedAssignmentIdState]);

  useEffect(() => {
    if (selectedCourseIdState === null) {
      setCourseStudents([]);
      setCourseAssignments([]);
      setSelectedAssignmentIdState(null);
      setCourseStudentsError(null);
      setAssignmentsError(null);
      return;
    }
    void loadCourseStudents(selectedCourseIdState);
    void loadAssignmentsForCourse(selectedCourseIdState);
  }, [selectedCourseIdState, loadAssignmentsForCourse, loadCourseStudents]);

  useEffect(() => {
    clearGradingState();
    if (selectedAssignmentIdState === null) {
      setSubmissions([]);
      setStudentsStatus([]);
      setSubmissionDataError(null);
      return;
    }
    void loadAssignmentData(selectedAssignmentIdState);
    const timer = window.setInterval(() => {
      void loadAssignmentData(selectedAssignmentIdState);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [clearGradingState, loadAssignmentData, selectedAssignmentIdState]);

  const value = useMemo<TeacherWorkspaceContextValue>(
    () => ({
      backendBaseUrl,
      courses,
      selectedCourseId: selectedCourseIdState,
      selectedAssignmentId: selectedAssignmentIdState,
      courseStudents,
      courseAssignments,
      submissions,
      studentsStatus,
      latestSolution,
      gradeAllSummary,
      modalResult,
      isModalOpen,
      gradingIds,
      viewingIds,
      solutionMessage,
      actionMessage,
      coursesError,
      assignmentsError,
      courseStudentsError,
      submissionDataError,
      isLoadingCourses,
      isLoadingAssignments,
      isLoadingCourseStudents,
      isLoadingSubmissionData,
      isUploadingSolution,
      isGradingAll,
      setSelectedCourseId,
      setSelectedAssignmentId,
      loadCourses,
      loadAssignmentsForCourse,
      loadCourseStudents,
      loadAssignmentData,
      applyBackendBaseUrl,
      uploadSolutionFile,
      gradeAllSelectedAssignment,
      gradeSubmissionById,
      viewSubmissionResult,
      closeResultModal,
    }),
    [
      actionMessage,
      applyBackendBaseUrl,
      assignmentsError,
      backendBaseUrl,
      closeResultModal,
      courseAssignments,
      courseStudents,
      courseStudentsError,
      courses,
      coursesError,
      gradeAllSelectedAssignment,
      gradeAllSummary,
      gradeSubmissionById,
      gradingIds,
      isGradingAll,
      isLoadingAssignments,
      isLoadingCourseStudents,
      isLoadingCourses,
      isLoadingSubmissionData,
      isUploadingSolution,
      isModalOpen,
      latestSolution,
      loadAssignmentData,
      loadAssignmentsForCourse,
      loadCourseStudents,
      loadCourses,
      modalResult,
      selectedAssignmentIdState,
      selectedCourseIdState,
      solutionMessage,
      studentsStatus,
      submissionDataError,
      submissions,
      uploadSolutionFile,
      viewSubmissionResult,
      viewingIds,
    ],
  );

  return (
    <TeacherWorkspaceContext.Provider value={value}>{children}</TeacherWorkspaceContext.Provider>
  );
};

export function useTeacherWorkspace(): TeacherWorkspaceContextValue {
  const context = useContext(TeacherWorkspaceContext);
  if (!context) {
    throw new Error("useTeacherWorkspace must be used within TeacherWorkspaceProvider");
  }
  return context;
}
