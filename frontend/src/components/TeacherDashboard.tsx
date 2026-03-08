import React, { useCallback, useEffect, useState } from "react";
import {
  type AnswerFileResponse,
  type Assignment,
  type Course,
  type GradeAllFailure,
  type GradeAllSummary,
  type GradeResult,
  type StudentAssignmentStatus,
  type StudentPublic,
  type Submission,
  createAssignment,
  createCourse,
  createStudent,
  fetchAssignmentsForCourse,
  fetchCourseStudents,
  fetchMyCourses,
  fetchSubmissionsForAssignment,
  fetchStudentsStatusForAssignment,
  fetchSubmissionResult,
  generateCourseJoinLink,
  gradeAllSubmissions,
  gradeSubmission,
  setBaseUrl,
  uploadSolution,
} from "../api";
import { useTeacherAuth } from "../auth/TeacherAuthContext";
import FileUploadArea from "./FileUploadArea";
import GradeResultModal from "./GradeResultModal";
import SubmissionList from "./SubmissionList";
import { useNavigate } from "react-router-dom";

type MessageType = "success" | "error" | "info";

interface StatusMessage {
  type: MessageType;
  text: string;
}

const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function isDocxFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".docx");
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function messageStyle(type: MessageType): React.CSSProperties {
  if (type === "success") {
    return {
      color: "#166534",
      backgroundColor: "#dcfce7",
      border: "1px solid #86efac",
    };
  }
  if (type === "error") {
    return {
      color: "#991b1b",
      backgroundColor: "#fee2e2",
      border: "1px solid #fca5a5",
    };
  }
  return {
    color: "#1e3a8a",
    backgroundColor: "#dbeafe",
    border: "1px solid #93c5fd",
  };
}

function getFailureReason(failure: GradeAllFailure): string {
  return failure.reason ?? failure.detail ?? "Unknown error";
}

function TeacherDashboard() {
  const navigate = useNavigate();
  const { teacher, logoutTeacher } = useTeacherAuth();

  const [baseUrlInput, setBaseUrlInput] = useState<string>(defaultBaseUrl);
  const [baseUrlMessage, setBaseUrlMessage] = useState<StatusMessage | null>(null);

  const [courses, setCourses] = useState<Course[]>([]);
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(null);
  const [courseStudents, setCourseStudents] = useState<StudentPublic[]>([]);

  const [courseAssignments, setCourseAssignments] = useState<Assignment[]>([]);
  const [selectedAssignmentId, setSelectedAssignmentId] = useState<number | null>(null);

  const [submissions, setSubmissions] = useState<Submission[]>([]);
  const [studentsStatus, setStudentsStatus] = useState<StudentAssignmentStatus[]>([]);

  const [solutionFiles, setSolutionFiles] = useState<File[]>([]);
  const [solutionAreaKey, setSolutionAreaKey] = useState<number>(0);
  const [latestSolution, setLatestSolution] = useState<AnswerFileResponse | null>(null);
  const [gradeAllSummary, setGradeAllSummary] = useState<GradeAllSummary | null>(null);
  const [modalResult, setModalResult] = useState<GradeResult | null>(null);
  const [isModalOpen, setIsModalOpen] = useState<boolean>(false);

  const [newCourseName, setNewCourseName] = useState<string>("");
  const [newCourseDescription, setNewCourseDescription] = useState<string>("");
  const [newStudentName, setNewStudentName] = useState<string>("");
  const [newStudentEmail, setNewStudentEmail] = useState<string>("");
  const [newStudentPassword, setNewStudentPassword] = useState<string>("");
  const [newAssignmentTitle, setNewAssignmentTitle] = useState<string>("");
  const [newAssignmentDescription, setNewAssignmentDescription] = useState<string>("");
  const [newAssignmentDueDate, setNewAssignmentDueDate] = useState<string>("");
  const [newAssignmentMaxScore, setNewAssignmentMaxScore] = useState<string>("");
  const [latestJoinUrl, setLatestJoinUrl] = useState<string>("");
  const [showAdvancedStudentTools, setShowAdvancedStudentTools] = useState<boolean>(false);

  const [gradingIds, setGradingIds] = useState<Set<number>>(new Set());
  const [viewingIds, setViewingIds] = useState<Set<number>>(new Set());

  const [isLoadingCourses, setIsLoadingCourses] = useState<boolean>(false);
  const [isLoadingAssignments, setIsLoadingAssignments] = useState<boolean>(false);
  const [isLoadingCourseStudents, setIsLoadingCourseStudents] = useState<boolean>(false);
  const [isLoadingSubmissionData, setIsLoadingSubmissionData] = useState<boolean>(false);
  const [isCreatingCourse, setIsCreatingCourse] = useState<boolean>(false);
  const [isCreatingStudent, setIsCreatingStudent] = useState<boolean>(false);
  const [isCreatingAssignment, setIsCreatingAssignment] = useState<boolean>(false);
  const [isGeneratingJoinLink, setIsGeneratingJoinLink] = useState<boolean>(false);
  const [isUploadingSolution, setIsUploadingSolution] = useState<boolean>(false);
  const [isGradingAll, setIsGradingAll] = useState<boolean>(false);

  const [courseMessage, setCourseMessage] = useState<StatusMessage | null>(null);
  const [joinLinkMessage, setJoinLinkMessage] = useState<StatusMessage | null>(null);
  const [studentMessage, setStudentMessage] = useState<StatusMessage | null>(null);
  const [assignmentMessage, setAssignmentMessage] = useState<StatusMessage | null>(null);
  const [solutionMessage, setSolutionMessage] = useState<StatusMessage | null>(null);
  const [actionMessage, setActionMessage] = useState<StatusMessage | null>(null);

  const loadCourses = useCallback(async () => {
    setIsLoadingCourses(true);
    try {
      const data = await fetchMyCourses();
      setCourses(data);
      setSelectedCourseId((prev) => {
        if (prev !== null && data.some((item) => item.id === prev)) {
          return prev;
        }
        return data.length > 0 ? data[0].id : null;
      });
    } catch (error) {
      setCourseMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsLoadingCourses(false);
    }
  }, []);

  const loadAssignmentsForCourse = useCallback(async (courseId: number) => {
    setIsLoadingAssignments(true);
    try {
      const data = await fetchAssignmentsForCourse(courseId);
      setCourseAssignments(data);
      setSelectedAssignmentId((prev) => {
        if (prev !== null && data.some((item) => item.id === prev)) {
          return prev;
        }
        return data.length > 0 ? data[0].id : null;
      });
    } catch (error) {
      setAssignmentMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsLoadingAssignments(false);
    }
  }, []);

  const loadCourseStudents = useCallback(async (courseId: number) => {
    setIsLoadingCourseStudents(true);
    try {
      const data = await fetchCourseStudents(courseId);
      setCourseStudents(data);
    } catch (error) {
      setStudentMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsLoadingCourseStudents(false);
    }
  }, []);

  const loadAssignmentData = useCallback(async (assignmentId: number) => {
    setIsLoadingSubmissionData(true);
    try {
      const [submissionData, statusData] = await Promise.all([
        fetchSubmissionsForAssignment(assignmentId),
        fetchStudentsStatusForAssignment(assignmentId),
      ]);
      setSubmissions(submissionData);
      setStudentsStatus(statusData);
    } catch (error) {
      setActionMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsLoadingSubmissionData(false);
    }
  }, []);

  useEffect(() => {
    setBaseUrl(defaultBaseUrl);
    void loadCourses();
  }, [loadCourses]);

  useEffect(() => {
    if (selectedCourseId === null) {
      setCourseStudents([]);
      setCourseAssignments([]);
      setSelectedAssignmentId(null);
      setLatestJoinUrl("");
      setJoinLinkMessage(null);
      return;
    }
    setLatestJoinUrl("");
    setJoinLinkMessage(null);
    void loadCourseStudents(selectedCourseId);
    void loadAssignmentsForCourse(selectedCourseId);
  }, [selectedCourseId, loadCourseStudents, loadAssignmentsForCourse]);

  useEffect(() => {
    if (selectedAssignmentId === null) {
      setSubmissions([]);
      setStudentsStatus([]);
      return;
    }
    void loadAssignmentData(selectedAssignmentId);
    const timer = window.setInterval(() => {
      void loadAssignmentData(selectedAssignmentId);
    }, 10000);
    return () => window.clearInterval(timer);
  }, [selectedAssignmentId, loadAssignmentData]);

  const handleApplyBaseUrl = async () => {
    try {
      setBaseUrl(baseUrlInput);
      setBaseUrlMessage({
        type: "success",
        text: `Backend URL updated to ${baseUrlInput}`,
      });
      await loadCourses();
      if (selectedCourseId !== null) {
        await loadAssignmentsForCourse(selectedCourseId);
      }
    } catch (error) {
      setBaseUrlMessage({
        type: "error",
        text: getErrorMessage(error),
      });
    }
  };

  const handleCreateCourse = async (event: React.FormEvent) => {
    event.preventDefault();
    setCourseMessage(null);
    try {
      setIsCreatingCourse(true);
      const course = await createCourse(
        newCourseName.trim(),
        newCourseDescription.trim() || undefined,
      );
      setCourses((prev) => [course, ...prev]);
      setSelectedCourseId(course.id);
      setNewCourseName("");
      setNewCourseDescription("");
      setCourseMessage({ type: "success", text: "班级创建成功。" });
    } catch (error) {
      setCourseMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsCreatingCourse(false);
    }
  };

  const handleGenerateJoinLink = async () => {
    setJoinLinkMessage(null);
    if (selectedCourseId === null) {
      setJoinLinkMessage({ type: "error", text: "请先选择班级。" });
      return;
    }
    try {
      setIsGeneratingJoinLink(true);
      const response = await generateCourseJoinLink(selectedCourseId);
      setLatestJoinUrl(response.join_url);
      setJoinLinkMessage({ type: "success", text: "加入链接已生成，旧链接已失效。" });
    } catch (error) {
      setJoinLinkMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsGeneratingJoinLink(false);
    }
  };

  const handleCopyJoinLink = async () => {
    if (!latestJoinUrl) {
      setJoinLinkMessage({ type: "error", text: "请先生成加入链接。" });
      return;
    }
    try {
      await navigator.clipboard.writeText(latestJoinUrl);
      setJoinLinkMessage({ type: "success", text: "链接已复制到剪贴板。" });
    } catch {
      setJoinLinkMessage({ type: "error", text: "复制失败，请手动复制链接。" });
    }
  };

  const handleCreateStudent = async (event: React.FormEvent) => {
    event.preventDefault();
    setStudentMessage(null);
    if (selectedCourseId === null) {
      setStudentMessage({ type: "error", text: "请先选择班级。" });
      return;
    }
    try {
      setIsCreatingStudent(true);
      const student = await createStudent(
        selectedCourseId,
        newStudentName.trim(),
        newStudentEmail.trim(),
        newStudentPassword,
      );
      setCourseStudents((prev) => [...prev, student]);
      setNewStudentName("");
      setNewStudentEmail("");
      setNewStudentPassword("");
      setStudentMessage({ type: "success", text: "学生已添加。" });
    } catch (error) {
      setStudentMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsCreatingStudent(false);
    }
  };

  const handleCreateAssignment = async (event: React.FormEvent) => {
    event.preventDefault();
    setAssignmentMessage(null);
    if (selectedCourseId === null) {
      setAssignmentMessage({ type: "error", text: "请先选择班级。" });
      return;
    }

    try {
      setIsCreatingAssignment(true);
      const title = newAssignmentTitle.trim();
      const description = newAssignmentDescription.trim() || undefined;
      const dueDate = newAssignmentDueDate.trim()
        ? new Date(newAssignmentDueDate).toISOString()
        : undefined;

      let maxScore: number | undefined;
      if (newAssignmentMaxScore.trim()) {
        const parsed = Number(newAssignmentMaxScore);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          setAssignmentMessage({ type: "error", text: "max_score 必须是正数。" });
          return;
        }
        maxScore = parsed;
      }

      const assignment = await createAssignment(selectedCourseId, {
        title,
        description,
        due_date: dueDate,
        max_score: maxScore,
      });

      await loadAssignmentsForCourse(selectedCourseId);
      setSelectedAssignmentId(assignment.id);
      setNewAssignmentTitle("");
      setNewAssignmentDescription("");
      setNewAssignmentDueDate("");
      setNewAssignmentMaxScore("");
      setAssignmentMessage({ type: "success", text: "作业创建成功。" });
    } catch (error) {
      setAssignmentMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsCreatingAssignment(false);
    }
  };

  const handleUploadSolution = async () => {
    setSolutionMessage(null);
    if (selectedAssignmentId === null) {
      setSolutionMessage({ type: "error", text: "请先选择作业。" });
      return;
    }
    if (solutionFiles.length === 0) {
      setSolutionMessage({ type: "error", text: "请选择官方答案 DOCX 文件。" });
      return;
    }
    const file = solutionFiles[0];
    if (!isDocxFile(file)) {
      setSolutionMessage({ type: "error", text: "官方答案必须是 .docx 文件。" });
      return;
    }

    try {
      setIsUploadingSolution(true);
      const response = await uploadSolution(selectedAssignmentId, file);
      setLatestSolution(response);
      setSolutionMessage({
        type: "success",
        text: `官方答案上传成功：${response.original_filename}`,
      });
      setSolutionFiles([]);
      setSolutionAreaKey((value) => value + 1);
    } catch (error) {
      setSolutionMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsUploadingSolution(false);
    }
  };

  const handleGradeSubmission = async (submissionId: number) => {
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
      if (selectedAssignmentId !== null) {
        await loadAssignmentData(selectedAssignmentId);
      }
    }
  };

  const handleViewResult = async (submissionId: number) => {
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
        text: message.includes("HTTP 404")
          ? "No grading result yet for this submission."
          : message,
      });
    } finally {
      setViewingIds((prev) => {
        const next = new Set(prev);
        next.delete(submissionId);
        return next;
      });
    }
  };

  const handleGradeAll = async () => {
    setActionMessage(null);
    setGradeAllSummary(null);
    if (selectedAssignmentId === null) {
      setActionMessage({ type: "error", text: "请先选择作业。" });
      return;
    }
    try {
      setIsGradingAll(true);
      const summary = await gradeAllSubmissions(selectedAssignmentId);
      setGradeAllSummary(summary);
      setActionMessage({
        type: "success",
        text: `批量批改完成：graded=${summary.graded}, failed=${summary.failed}`,
      });
      await loadAssignmentData(selectedAssignmentId);
    } catch (error) {
      setActionMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsGradingAll(false);
    }
  };

  return (
    <div style={panelStyle}>
      <section style={cardStyle}>
        <div style={headerRowStyle}>
          <div>
            <h2 style={sectionTitleStyle}>教师会话</h2>
            <p style={contextHintStyle}>
              {teacher ? `${teacher.name} (${teacher.email})` : "Unknown teacher"}
            </p>
          </div>
          <button
            type="button"
            style={buttonSecondaryStyle}
            onClick={() => {
              logoutTeacher();
              navigate("/teacher/login", { replace: true });
            }}
          >
            退出登录
          </button>
        </div>

        <div style={{ ...gridStyle, marginTop: "12px" }}>
          <label style={{ ...fieldStyle, gridColumn: "1 / span 2" }}>
            <span style={labelTextStyle}>Backend Base URL</span>
            <input
              type="text"
              value={baseUrlInput}
              onChange={(event) => setBaseUrlInput(event.target.value)}
              placeholder="http://localhost:8000"
              style={inputStyle}
            />
          </label>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button type="button" onClick={handleApplyBaseUrl} style={buttonSecondaryStyle}>
              Apply
            </button>
          </div>
        </div>
        {baseUrlMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(baseUrlMessage.type) }}>
            {baseUrlMessage.text}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>班级管理</h2>
        <div style={splitGridStyle}>
          <div>
            <h3 style={subTitleStyle}>已有班级</h3>
            <div style={{ marginBottom: "10px" }}>
              <button
                type="button"
                style={buttonSecondaryStyle}
                disabled={isLoadingCourses}
                onClick={() => void loadCourses()}
              >
                {isLoadingCourses ? "Loading..." : "Refresh courses"}
              </button>
            </div>
            {courses.length === 0 ? (
              <div style={emptyBoxStyle}>暂无班级</div>
            ) : (
              <div style={{ display: "grid", gap: "8px" }}>
                {courses.map((course) => (
                  <button
                    key={course.id}
                    type="button"
                    onClick={() => setSelectedCourseId(course.id)}
                    style={{
                      ...courseButtonStyle,
                      ...(selectedCourseId === course.id ? courseButtonActiveStyle : {}),
                    }}
                  >
                    <strong>#{course.id}</strong> {course.name}
                    {course.description ? ` - ${course.description}` : ""}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <h3 style={subTitleStyle}>创建班级</h3>
            <form onSubmit={handleCreateCourse} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Course Name</span>
                <input
                  style={inputStyle}
                  value={newCourseName}
                  onChange={(event) => setNewCourseName(event.target.value)}
                  required
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Description (optional)</span>
                <input
                  style={inputStyle}
                  value={newCourseDescription}
                  onChange={(event) => setNewCourseDescription(event.target.value)}
                />
              </label>
              <button type="submit" style={buttonPrimaryStyle} disabled={isCreatingCourse}>
                {isCreatingCourse ? "Creating..." : "Create Course"}
              </button>
            </form>
          </div>
        </div>
        <div style={{ marginTop: "12px", ...inlineInfoStyle }}>
          <div style={{ marginBottom: "10px", fontWeight: 600 }}>学生加入链接</div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              style={buttonSecondaryStyle}
              onClick={handleGenerateJoinLink}
              disabled={selectedCourseId === null || isGeneratingJoinLink}
            >
              {isGeneratingJoinLink ? "Generating..." : "生成加入链接"}
            </button>
            <input
              style={{ ...inputStyle, minWidth: "360px", flex: 1 }}
              value={latestJoinUrl}
              placeholder="生成后会显示可分享给学生的链接"
              readOnly
            />
            <button
              type="button"
              style={buttonSecondaryStyle}
              onClick={() => void handleCopyJoinLink()}
              disabled={!latestJoinUrl}
            >
              复制
            </button>
          </div>
          <div style={{ marginTop: "8px", color: "#334155", fontSize: "0.88rem" }}>
            重新生成会立即覆盖旧链接，旧链接将失效。
          </div>
        </div>
        {courseMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(courseMessage.type) }}>
            {courseMessage.text}
          </div>
        )}
        {joinLinkMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(joinLinkMessage.type) }}>
            {joinLinkMessage.text}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>学生名单管理</h2>
        {selectedCourseId === null ? (
          <div style={emptyBoxStyle}>请先在上方选择班级</div>
        ) : (
          <div style={splitGridStyle}>
            <div>
              <h3 style={subTitleStyle}>班级学生列表</h3>
              {isLoadingCourseStudents ? (
                <div style={emptyBoxStyle}>加载中...</div>
              ) : courseStudents.length === 0 ? (
                <div style={emptyBoxStyle}>该班级暂无学生</div>
              ) : (
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={thStyle}>ID</th>
                      <th style={thStyle}>Name</th>
                      <th style={thStyle}>Email</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courseStudents.map((student) => (
                      <tr key={student.id}>
                        <td style={tdStyle}>{student.id}</td>
                        <td style={tdStyle}>{student.name}</td>
                        <td style={tdStyle}>{student.email}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            <div>
              <h3 style={subTitleStyle}>高级管理（默认隐藏）</h3>
              <button
                type="button"
                style={buttonSecondaryStyle}
                onClick={() => setShowAdvancedStudentTools((prev) => !prev)}
              >
                {showAdvancedStudentTools ? "隐藏手动添加学生" : "显示手动添加学生"}
              </button>
              {showAdvancedStudentTools && (
                <form onSubmit={handleCreateStudent} style={{ ...formStyle, marginTop: "10px" }}>
                  <label style={fieldStyle}>
                    <span style={labelTextStyle}>Name</span>
                    <input
                      style={inputStyle}
                      value={newStudentName}
                      onChange={(event) => setNewStudentName(event.target.value)}
                      required
                    />
                  </label>
                  <label style={fieldStyle}>
                    <span style={labelTextStyle}>Email</span>
                    <input
                      style={inputStyle}
                      type="email"
                      value={newStudentEmail}
                      onChange={(event) => setNewStudentEmail(event.target.value)}
                      required
                    />
                  </label>
                  <label style={fieldStyle}>
                    <span style={labelTextStyle}>Initial Password</span>
                    <input
                      style={inputStyle}
                      type="password"
                      value={newStudentPassword}
                      onChange={(event) => setNewStudentPassword(event.target.value)}
                      required
                    />
                  </label>
                  <button type="submit" style={buttonPrimaryStyle} disabled={isCreatingStudent}>
                    {isCreatingStudent ? "Creating..." : "Create Student"}
                  </button>
                </form>
              )}
            </div>
          </div>
        )}
        {studentMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(studentMessage.type) }}>
            {studentMessage.text}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>作业发布与管理</h2>
        <div style={splitGridStyle}>
          <div>
            <h3 style={subTitleStyle}>当前班级作业</h3>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "10px" }}>
              <select
                style={{ ...inputStyle, minWidth: "280px" }}
                value={selectedAssignmentId ?? ""}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setSelectedAssignmentId(Number.isFinite(value) && value > 0 ? value : null);
                }}
                disabled={isLoadingAssignments || courseAssignments.length === 0}
              >
                {courseAssignments.length === 0 ? (
                  <option value="">No assignments</option>
                ) : (
                  courseAssignments.map((assignment) => (
                    <option key={assignment.id} value={assignment.id}>
                      #{assignment.id} - {assignment.title}
                    </option>
                  ))
                )}
              </select>
              <button
                type="button"
                style={buttonSecondaryStyle}
                disabled={isLoadingAssignments || selectedCourseId === null}
                onClick={() => {
                  if (selectedCourseId !== null) {
                    void loadAssignmentsForCourse(selectedCourseId);
                  }
                }}
              >
                {isLoadingAssignments ? "Loading..." : "Refresh assignments"}
              </button>
            </div>
            {courseAssignments.length === 0 ? (
              <div style={emptyBoxStyle}>当前班级暂无作业。</div>
            ) : (
              <div style={{ overflowX: "auto" }}>
                <table style={tableStyle}>
                  <thead>
                    <tr>
                      <th style={thStyle}>ID</th>
                      <th style={thStyle}>Title</th>
                      <th style={thStyle}>Due Date</th>
                      <th style={thStyle}>Max Score</th>
                      <th style={thStyle}>Created At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {courseAssignments.map((assignment) => (
                      <tr key={`assignment-row-${assignment.id}`}>
                        <td style={tdStyle}>{assignment.id}</td>
                        <td style={tdStyle}>{assignment.title}</td>
                        <td style={tdStyle}>{formatDateTime(assignment.due_date)}</td>
                        <td style={tdStyle}>{assignment.max_score ?? "-"}</td>
                        <td style={tdStyle}>{formatDateTime(assignment.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {selectedAssignmentId && (
              <div style={inlineInfoStyle}>
                正在轮询刷新提交状态（每 10 秒）
              </div>
            )}
          </div>
          <div>
            <h3 style={subTitleStyle}>创建作业</h3>
            <form onSubmit={handleCreateAssignment} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Title</span>
                <input
                  style={inputStyle}
                  value={newAssignmentTitle}
                  onChange={(event) => setNewAssignmentTitle(event.target.value)}
                  required
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Description (optional)</span>
                <input
                  style={inputStyle}
                  value={newAssignmentDescription}
                  onChange={(event) => setNewAssignmentDescription(event.target.value)}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Due Date (optional)</span>
                <input
                  style={inputStyle}
                  type="datetime-local"
                  value={newAssignmentDueDate}
                  onChange={(event) => setNewAssignmentDueDate(event.target.value)}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Max Score (optional)</span>
                <input
                  style={inputStyle}
                  type="number"
                  min="0"
                  step="0.5"
                  placeholder="默认 100"
                  value={newAssignmentMaxScore}
                  onChange={(event) => setNewAssignmentMaxScore(event.target.value)}
                />
              </label>
              <button type="submit" style={buttonPrimaryStyle} disabled={isCreatingAssignment}>
                {isCreatingAssignment ? "Creating..." : "Create Assignment"}
              </button>
            </form>
          </div>
        </div>
        {assignmentMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(assignmentMessage.type) }}>
            {assignmentMessage.text}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>作业批改：官方答案上传 + 批改控制</h2>
        <FileUploadArea
          key={`solution-area-${solutionAreaKey}`}
          label="Official solution DOCX"
          accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          multiple={false}
          onFilesSelected={setSolutionFiles}
        />
        <div style={{ marginTop: "12px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={handleUploadSolution}
            disabled={isUploadingSolution || selectedAssignmentId === null}
            style={buttonPrimaryStyle}
          >
            {isUploadingSolution ? "Uploading..." : "Upload Solution"}
          </button>
          <button
            type="button"
            onClick={handleGradeAll}
            disabled={isGradingAll || selectedAssignmentId === null}
            style={buttonSecondaryStyle}
          >
            {isGradingAll ? "Grading all..." : "Grade all submissions"}
          </button>
        </div>

        {solutionMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(solutionMessage.type) }}>
            {solutionMessage.text}
          </div>
        )}
        {actionMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(actionMessage.type) }}>
            {actionMessage.text}
          </div>
        )}
        {latestSolution && (
          <div style={debugInfoStyle}>
            <div>
              <strong>Latest qwen_file_id:</strong> {latestSolution.qwen_file_id}
            </div>
            <div>
              <strong>Uploaded at:</strong> {latestSolution.uploaded_at}
            </div>
          </div>
        )}

        {gradeAllSummary && (
          <div style={summaryPanelStyle}>
            <div style={summaryGridStyle}>
              <div>
                <strong>Total:</strong> {gradeAllSummary.total}
              </div>
              <div>
                <strong>Graded:</strong> {gradeAllSummary.graded}
              </div>
              <div>
                <strong>Failed:</strong> {gradeAllSummary.failed}
              </div>
              <div>
                <strong>Skipped:</strong> {gradeAllSummary.skipped}
              </div>
            </div>
            {gradeAllSummary.failures.length > 0 && (
              <div style={{ marginTop: "10px" }}>
                <strong>Failures:</strong>
                <ul style={{ margin: "8px 0 0", paddingLeft: "20px" }}>
                  {gradeAllSummary.failures.map((failure) => (
                    <li key={`failure-${failure.submission_id}`}>
                      #{failure.submission_id}: {getFailureReason(failure)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>学生交作业状态（实时）</h2>
        {selectedAssignmentId === null ? (
          <div style={emptyBoxStyle}>请选择作业后查看状态。</div>
        ) : isLoadingSubmissionData ? (
          <div style={emptyBoxStyle}>加载中...</div>
        ) : studentsStatus.length === 0 ? (
          <div style={emptyBoxStyle}>当前班级暂无学生或暂无状态数据。</div>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Student Name</th>
                <th style={thStyle}>Email</th>
                <th style={thStyle}>Has Submitted</th>
                <th style={thStyle}>Submission Status</th>
                <th style={thStyle}>Score</th>
              </tr>
            </thead>
            <tbody>
              {studentsStatus.map((item) => (
                <tr key={item.student_id}>
                  <td style={tdStyle}>{item.student_name}</td>
                  <td style={tdStyle}>{item.student_email}</td>
                  <td style={tdStyle}>{item.has_submitted ? "Yes" : "No"}</td>
                  <td style={tdStyle}>{item.submission_status ?? "-"}</td>
                  <td style={tdStyle}>
                    {item.submission_status === "needs_manual_review" &&
                    item.total_score !== null &&
                    item.max_total_score !== null
                      ? `自动评分小计 ${item.total_score} / ${item.max_total_score}`
                      : item.total_score !== null && item.max_total_score !== null
                        ? `${item.total_score} / ${item.max_total_score}`
                        : "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>提交记录（后端）</h2>
        <SubmissionList
          submissions={submissions}
          gradingIds={gradingIds}
          viewingIds={viewingIds}
          onGrade={handleGradeSubmission}
          onViewResult={handleViewResult}
        />
      </section>

      <GradeResultModal
        isOpen={isModalOpen}
        result={modalResult}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  display: "grid",
  gap: "16px",
};

const cardStyle: React.CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "16px",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
};

const sectionTitleStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "12px",
  fontSize: "1.2rem",
  color: "#0f172a",
};

const subTitleStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "10px",
  fontSize: "1rem",
  color: "#1e293b",
};

const contextHintStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: 0,
  color: "#475569",
  fontSize: "0.92rem",
  lineHeight: 1.5,
};

const headerRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap",
};

const gridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
};

const splitGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
  gap: "14px",
};

const formStyle: React.CSSProperties = {
  display: "grid",
  gap: "10px",
};

const fieldStyle: React.CSSProperties = {
  display: "grid",
  gap: "6px",
};

const labelTextStyle: React.CSSProperties = {
  fontSize: "0.9rem",
  color: "#334155",
};

const inputStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.95rem",
  outline: "none",
};

const buttonPrimaryStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "8px 12px",
  cursor: "pointer",
};

const buttonSecondaryStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  backgroundColor: "#ffffff",
  color: "#0f172a",
  padding: "8px 12px",
  cursor: "pointer",
};

const alertBaseStyle: React.CSSProperties = {
  marginTop: "12px",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.92rem",
};

const debugInfoStyle: React.CSSProperties = {
  marginTop: "10px",
  fontSize: "0.9rem",
  color: "#334155",
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "8px",
  padding: "10px",
  display: "grid",
  gap: "4px",
};

const summaryPanelStyle: React.CSSProperties = {
  marginTop: "12px",
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "10px",
  padding: "10px 12px",
  color: "#0f172a",
};

const summaryGridStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "8px",
};

const emptyBoxStyle: React.CSSProperties = {
  border: "1px dashed #cbd5e1",
  borderRadius: "8px",
  padding: "12px",
  color: "#64748b",
  backgroundColor: "#f8fafc",
};

const inlineInfoStyle: React.CSSProperties = {
  color: "#1e3a8a",
  backgroundColor: "#dbeafe",
  border: "1px solid #93c5fd",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.9rem",
};

const courseButtonStyle: React.CSSProperties = {
  textAlign: "left",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#0f172a",
  borderRadius: "8px",
  padding: "8px 10px",
  cursor: "pointer",
};

const courseButtonActiveStyle: React.CSSProperties = {
  borderColor: "#60a5fa",
  backgroundColor: "#eff6ff",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  border: "1px solid #e2e8f0",
  backgroundColor: "#ffffff",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px",
  backgroundColor: "#f8fafc",
  borderBottom: "1px solid #e2e8f0",
  color: "#334155",
  fontSize: "0.9rem",
};

const tdStyle: React.CSSProperties = {
  padding: "10px",
  borderBottom: "1px solid #e2e8f0",
  color: "#0f172a",
  fontSize: "0.92rem",
};

export default TeacherDashboard;
