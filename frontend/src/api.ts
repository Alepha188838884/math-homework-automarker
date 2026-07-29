import { computeExpiresAt } from "./auth/jwt";
import {
  clearStudentSession,
  clearTeacherSession,
  loadStudentSession,
  loadTeacherSession,
  saveStudentSession,
  saveTeacherSession,
  setStudentProfileInStorage,
  setTeacherProfileInStorage,
} from "./auth/storage";

export type AuthRole = "none" | "teacher" | "student";

export interface TeacherPublic {
  id: number;
  name: string;
  email: string;
}

export interface StudentPublic {
  id: number;
  name: string;
  email: string;
  course_id: number;
}

export interface TeacherLoginResponse {
  access_token: string;
  token_type: string;
  teacher: TeacherPublic;
}

export interface StudentLoginResponse {
  access_token: string;
  token_type: string;
  student: StudentPublic;
}

export interface Course {
  id: number;
  teacher_id: number;
  name: string;
  description?: string | null;
  created_at: string;
}

export interface CourseJoinInfo {
  course_id: number;
  course_name: string;
  teacher_name?: string | null;
}

export interface JoinLinkResponse {
  course_id: number;
  join_token: string;
  join_url: string;
}

export interface StudentJoinRequest {
  name: string;
  email: string;
  password: string;
}

export interface StudentJoinResponse {
  student_id: number;
  course_id: number;
  email: string;
  access_token?: string | null;
  token_type?: string | null;
}

export interface Assignment {
  id: number;
  teacher_id: number;
  course_id: number;
  title: string;
  description?: string | null;
  due_date?: string | null;
  max_score?: number | null;
  created_at: string;
}

export interface AnswerFileResponse {
  id: number;
  assignment_id: number;
  original_filename: string;
  file_path: string;
  qwen_file_id: string | null;
  uploaded_at: string;
  updated_at?: string;
}

export type SubmissionStatus =
  | "uploaded"
  | "failed_upload"
  | "grading"
  | "graded"
  | "needs_manual_review"
  | "failed_grading";

export interface Submission {
  id: number;
  assignment_id: number;
  student_id: number;
  original_filename: string;
  status: SubmissionStatus;
  created_at: string;
  graded_at?: string | null;
  file_path?: string;
  qwen_file_id?: string | null;
  error_message?: string | null;
  updated_at?: string;
}

export interface GradeQuestion {
  number: number;
  is_correct: boolean | null;
  score: number | null;
  max_score: number;
  comment?: string | null;
}

export interface GradeResult {
  submission_id: number;
  status?: SubmissionStatus;
  model_name?: string;
  graded_at?: string | null;
  total_score: number;
  max_total_score: number;
  questions: GradeQuestion[];
}

export interface GradeAllFailure {
  submission_id: number;
  reason?: string;
  detail?: string;
}

export interface GradeAllSummary {
  assignment_id: number;
  total: number;
  graded: number;
  failed: number;
  skipped: number;
  failures: GradeAllFailure[];
}

export interface StudentAssignmentStatus {
  student_id: number;
  student_name: string;
  student_email: string;
  has_submitted: boolean;
  submission_id: number | null;
  submission_status: SubmissionStatus | null;
  total_score: number | null;
  max_total_score: number | null;
}

export interface StudentAssignmentOverview {
  assignment_id: number;
  title: string;
  description?: string | null;
  created_at: string;
  due_date?: string | null;
  max_score?: number | null;
  has_submitted: boolean;
  submission_id?: number | null;
  submission_status?: SubmissionStatus | null;
  total_score?: number | null;
  max_total_score?: number | null;
}

let API_BASE_URL = "http://localhost:8000";

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, "");
}

export function setBaseUrl(baseUrl: string): void {
  const normalized = normalizeBaseUrl(baseUrl);
  if (!normalized) {
    throw new Error("Backend base URL cannot be empty.");
  }
  API_BASE_URL = normalized;
}

function buildUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function setTeacherToken(token: string): void {
  const existing = loadTeacherSession<TeacherPublic>();
  saveTeacherSession<TeacherPublic>({
    token,
    expiresAt: computeExpiresAt(token),
    profile: existing?.profile ?? null,
    rememberMe: true,
  });
}

export function getTeacherToken(): string | null {
  return loadTeacherSession<TeacherPublic>()?.token ?? null;
}

export function clearTeacherToken(): void {
  clearTeacherSession();
}

export function setStudentToken(token: string): void {
  const existing = loadStudentSession<StudentPublic>();
  saveStudentSession<StudentPublic>({
    token,
    expiresAt: computeExpiresAt(token),
    profile: existing?.profile ?? null,
    rememberMe: true,
  });
}

export function getStudentToken(): string | null {
  return loadStudentSession<StudentPublic>()?.token ?? null;
}

export function clearStudentToken(): void {
  clearStudentSession();
}

export function setTeacherProfile(profile: TeacherPublic): void {
  setTeacherProfileInStorage(profile);
}

export function getTeacherProfile(): TeacherPublic | null {
  return loadTeacherSession<TeacherPublic>()?.profile ?? null;
}

export function setStudentProfile(profile: StudentPublic): void {
  setStudentProfileInStorage(profile);
}

export function getStudentProfile(): StudentPublic | null {
  return loadStudentSession<StudentPublic>()?.profile ?? null;
}

async function extractErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("content-type") ?? "";

  if (contentType.includes("application/json")) {
    try {
      const body = (await response.json()) as Record<string, unknown>;
      const detail = body.detail;
      const message = body.message;
      if (typeof detail === "string" && detail.trim()) {
        return detail;
      }
      if (Array.isArray(detail) && detail.length > 0) {
        const parsed = detail
          .map((item) => {
            if (typeof item === "string") {
              return item;
            }
            if (item && typeof item === "object") {
              const entry = item as Record<string, unknown>;
              const msg = entry.msg;
              const loc = entry.loc;
              const locText = Array.isArray(loc)
                ? loc
                    .map((segment) => String(segment))
                    .filter((segment) => segment !== "body")
                    .join(".")
                : "";
              if (typeof msg === "string" && msg.trim()) {
                return locText ? `${locText}: ${msg}` : msg;
              }
            }
            return "";
          })
          .filter((text) => text.trim().length > 0);
        if (parsed.length > 0) {
          return parsed.join("; ");
        }
      }
      if (typeof message === "string" && message.trim()) {
        return message;
      }
    } catch {
      // Ignore parsing error and fallback to text.
    }
  }

  try {
    const text = await response.text();
    if (text.trim()) {
      return text;
    }
  } catch {
    // Ignore text read error and fallback.
  }

  return response.statusText || "Request failed";
}

function buildAuthHeaders(authRole: AuthRole): HeadersInit {
  if (authRole === "none") {
    return {};
  }
  const token = authRole === "teacher" ? getTeacherToken() : getStudentToken();
  if (!token) {
    return {};
  }
  return { Authorization: `Bearer ${token}` };
}

const DEFAULT_TIMEOUT_MS = 30_000;

async function requestJson<T>(
  path: string,
  init: RequestInit,
  authRole: AuthRole = "none",
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): Promise<T> {
  const mergedHeaders: HeadersInit = {
    ...buildAuthHeaders(authRole),
    ...(init.headers ?? {}),
  };

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  // Merge with any existing signal from caller
  const existingSignal = init.signal;
  if (existingSignal) {
    existingSignal.addEventListener("abort", () => controller.abort());
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path), {
      ...init,
      headers: mergedHeaders,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted && !(existingSignal?.aborted)) {
      throw new Error(`请求超时（${timeoutMs / 1000} 秒），请检查网络连接或稍后重试。`);
    }
    const reason = error instanceof Error ? error.message : "Network error";
    throw new Error(
      `无法连接后端服务 (${API_BASE_URL})，请检查后端是否已启动或 CORS/端口是否匹配。原始错误: ${reason}`,
    );
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      if (authRole === "teacher") {
        clearTeacherSession();
      } else if (authRole === "student") {
        clearStudentSession();
      }
    }
    const message = await extractErrorMessage(response);
    throw new Error(`HTTP ${response.status}: ${message}`);
  }

  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error("Server did not return JSON.");
  }
  return (await response.json()) as T;
}

export async function bootstrapTeacher(
  name: string,
  email: string,
  password: string,
): Promise<TeacherLoginResponse> {
  return requestJson<TeacherLoginResponse>(
    "/auth/bootstrap-teacher",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    },
    "none",
  );
}

export async function teacherLogin(
  email: string,
  password: string,
): Promise<TeacherLoginResponse> {
  return requestJson<TeacherLoginResponse>(
    "/auth/teacher/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    "none",
  );
}

export async function teacherEntry(
  email: string,
  password: string,
  name?: string,
): Promise<TeacherLoginResponse> {
  return requestJson<TeacherLoginResponse>(
    "/auth/teacher/entry",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    },
    "none",
  );
}

export async function studentLogin(
  email: string,
  password: string,
): Promise<StudentLoginResponse> {
  return requestJson<StudentLoginResponse>(
    "/auth/student/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    },
    "none",
  );
}

export async function studentEntry(
  email: string,
  password: string,
  options?: {
    name?: string;
    assignment_id?: number;
  },
): Promise<StudentLoginResponse> {
  return requestJson<StudentLoginResponse>(
    "/auth/student/entry",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email,
        password,
        name: options?.name,
        assignment_id: options?.assignment_id,
      }),
    },
    "none",
  );
}

export async function fetchMyCourses(): Promise<Course[]> {
  return requestJson<Course[]>(
    "/teachers/me/courses",
    {
      method: "GET",
    },
    "teacher",
  );
}

export async function createCourse(
  name: string,
  description?: string,
): Promise<Course> {
  return requestJson<Course>(
    "/teachers/me/courses",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, description }),
    },
    "teacher",
  );
}

export async function generateCourseJoinLink(courseId: number): Promise<JoinLinkResponse> {
  return requestJson<JoinLinkResponse>(
    `/courses/${courseId}/join-link`,
    {
      method: "POST",
    },
    "teacher",
  );
}

export async function fetchCourseJoinInfo(joinToken: string): Promise<CourseJoinInfo> {
  return requestJson<CourseJoinInfo>(
    `/courses/join/${joinToken}`,
    {
      method: "GET",
    },
    "none",
  );
}

export async function registerStudentViaJoinToken(
  joinToken: string,
  payload: StudentJoinRequest,
): Promise<StudentJoinResponse> {
  return requestJson<StudentJoinResponse>(
    `/courses/join/${joinToken}/register`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "none",
  );
}

export async function fetchCourseStudents(
  courseId: number,
): Promise<StudentPublic[]> {
  return requestJson<StudentPublic[]>(
    `/courses/${courseId}/students`,
    {
      method: "GET",
    },
    "teacher",
  );
}

export async function createStudent(
  courseId: number,
  name: string,
  email: string,
  password: string,
): Promise<StudentPublic> {
  return requestJson<StudentPublic>(
    `/courses/${courseId}/students`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    },
    "teacher",
  );
}

export async function createAssignment(
  courseId: number,
  payload: {
    title: string;
    description?: string;
    due_date?: string;
    max_score?: number;
  },
): Promise<Assignment> {
  return requestJson<Assignment>(
    `/courses/${courseId}/assignments`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
    "teacher",
  );
}

export async function fetchAssignmentsForCourse(
  courseId: number,
): Promise<Assignment[]> {
  return requestJson<Assignment[]>(
    `/courses/${courseId}/assignments`,
    {
      method: "GET",
    },
    "teacher",
  );
}

export async function fetchAssignments(): Promise<Assignment[]> {
  return requestJson<Assignment[]>(
    "/assignments",
    {
      method: "GET",
    },
    "teacher",
  );
}

export async function fetchSubmissionsForAssignment(
  assignmentId: number,
): Promise<Submission[]> {
  return requestJson<Submission[]>(
    `/assignments/${assignmentId}/submissions`,
    {
      method: "GET",
    },
    "teacher",
  );
}

export async function fetchStudentsStatusForAssignment(
  assignmentId: number,
): Promise<StudentAssignmentStatus[]> {
  return requestJson<StudentAssignmentStatus[]>(
    `/assignments/${assignmentId}/students-status`,
    {
      method: "GET",
    },
    "teacher",
  );
}

export async function uploadSolution(
  assignmentId: number,
  file: File,
): Promise<AnswerFileResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return requestJson<AnswerFileResponse>(
    `/assignments/${assignmentId}/solution`,
    {
      method: "POST",
      body: formData,
    },
    "teacher",
    120_000,
  );
}

export async function uploadSubmission(
  assignmentId: number,
  studentId: number | string,
  file: File,
): Promise<Submission> {
  const formData = new FormData();
  formData.append("student_id", String(studentId));
  formData.append("file", file);

  return requestJson<Submission>(
    `/assignments/${assignmentId}/submissions`,
    {
      method: "POST",
      body: formData,
    },
    "teacher",
    120_000,
  );
}

export async function uploadSubmissionForMe(
  assignmentId: number,
  file: File,
): Promise<Submission> {
  const formData = new FormData();
  formData.append("file", file);
  return requestJson<Submission>(
    `/assignments/${assignmentId}/submissions/me`,
    {
      method: "POST",
      body: formData,
    },
    "student",
    120_000,
  );
}

export async function fetchMyAssignmentsOverview(): Promise<StudentAssignmentOverview[]> {
  return requestJson<StudentAssignmentOverview[]>(
    "/students/me/assignments",
    {
      method: "GET",
    },
    "student",
  );
}

export async function gradeSubmission(
  submissionId: number,
): Promise<GradeResult> {
  return requestJson<GradeResult>(
    `/submissions/${submissionId}/grade`,
    {
      method: "POST",
    },
    "teacher",
    120_000,
  );
}

export async function gradeAllSubmissions(
  assignmentId: number,
): Promise<GradeAllSummary> {
  return requestJson<GradeAllSummary>(
    `/assignments/${assignmentId}/grade-all`,
    {
      method: "POST",
    },
    "teacher",
    300_000,
  );
}

export async function fetchSubmissionResult(
  submissionId: number,
): Promise<GradeResult> {
  return requestJson<GradeResult>(
    `/submissions/${submissionId}/result`,
    {
      method: "GET",
    },
    "teacher",
  );
}
