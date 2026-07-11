import React, { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { setBaseUrl } from "./api";
import { useStudentAuth } from "./auth/StudentAuthContext";
import { useTeacherAuth } from "./auth/TeacherAuthContext";
import ErrorBoundary from "./components/ErrorBoundary";
import StudentJoinPage from "./components/StudentJoinPage";
import StudentLoginPage from "./components/StudentLoginPage";
import StudentUploadPage from "./components/StudentUploadPage";
import TeacherLoginPage from "./components/TeacherLoginPage";
import TeacherLayout from "./teacher/TeacherLayout";
import { TeacherWorkspaceProvider } from "./teacher/TeacherWorkspaceContext";
import TeacherAssignmentsPage from "./teacher/pages/TeacherAssignmentsPage";
import TeacherCoursesPage from "./teacher/pages/TeacherCoursesPage";
import TeacherGradingPage from "./teacher/pages/TeacherGradingPage";
import TeacherSubmissionRecordsPage from "./teacher/pages/TeacherSubmissionRecordsPage";
import TeacherSubmissionStatusPage from "./teacher/pages/TeacherSubmissionStatusPage";
import TeacherStudentsPage from "./teacher/pages/TeacherStudentsPage";

const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const RequireTeacherAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { ready, isAuthenticated } = useTeacherAuth();
  if (!ready) return <div className="loading-box">正在恢复教师会话...</div>;
  if (!isAuthenticated) return <Navigate to="/teacher/login" replace />;
  return <>{children}</>;
};

const RequireStudentAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { ready, isAuthenticated } = useStudentAuth();
  const location = useLocation();
  if (!ready) return <div className="loading-box">正在恢复学生会话...</div>;
  if (!isAuthenticated) return <Navigate to={`/student/login${location.search}`} replace />;
  return <>{children}</>;
};

function AppHeader() {
  const location = useLocation();
  const isTeacherDashboard = location.pathname.startsWith("/teacher") &&
    !location.pathname.includes("/login");

  if (isTeacherDashboard) return null;

  return (
    <header className="page-header">
      <div>
        <h1 className="page-title">数学作业自动批改系统</h1>
        <p className="page-subtitle">
          通用数学作业批改平台：老师管理班级与作业，学生登录后提交 PDF。
        </p>
      </div>
    </header>
  );
}

function App() {
  useEffect(() => {
    setBaseUrl(defaultBaseUrl);
  }, []);

  return (
    <div className="page-bg">
      <div className="page-container">
        <AppHeader />
        <ErrorBoundary>
          <Routes>
            <Route path="/" element={<Navigate to="/teacher/login" replace />} />
            <Route path="/teacher/login" element={<TeacherLoginPage />} />
            <Route
              path="/teacher"
              element={
                <RequireTeacherAuth>
                  <TeacherWorkspaceProvider>
                    <TeacherLayout />
                  </TeacherWorkspaceProvider>
                </RequireTeacherAuth>
              }
            >
              <Route index element={<Navigate to="courses" replace />} />
              <Route path="dashboard" element={<Navigate to="/teacher/courses" replace />} />
              <Route path="courses" element={<TeacherCoursesPage />} />
              <Route path="students" element={<TeacherStudentsPage />} />
              <Route path="assignments" element={<TeacherAssignmentsPage />} />
              <Route path="grading" element={<TeacherGradingPage />} />
              <Route path="submission-status" element={<TeacherSubmissionStatusPage />} />
              <Route path="submission-records" element={<TeacherSubmissionRecordsPage />} />
              <Route path="*" element={<Navigate to="/teacher/courses" replace />} />
            </Route>

            <Route path="/student/login" element={<StudentLoginPage />} />
            <Route path="/student/join/:joinToken" element={<StudentJoinPage />} />
            <Route
              path="/student"
              element={
                <RequireStudentAuth>
                  <StudentUploadPage />
                </RequireStudentAuth>
              }
            />
            <Route path="/student/home" element={<Navigate to="/student" replace />} />
            <Route path="*" element={<Navigate to="/teacher/login" replace />} />
          </Routes>
        </ErrorBoundary>
      </div>
    </div>
  );
}

export default App;
