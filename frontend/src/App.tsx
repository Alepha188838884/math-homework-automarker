import React, { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { setBaseUrl } from "./api";
import { useStudentAuth } from "./auth/StudentAuthContext";
import { useTeacherAuth } from "./auth/TeacherAuthContext";
import StudentJoinPage from "./components/StudentJoinPage";
import StudentLoginPage from "./components/StudentLoginPage";
import StudentUploadPage from "./components/StudentUploadPage";
import TeacherDashboard from "./components/TeacherDashboard";
import TeacherLoginPage from "./components/TeacherLoginPage";

const defaultBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

const pageStyle: React.CSSProperties = {
  minHeight: "100vh",
  background:
    "radial-gradient(circle at top left, #f0f9ff 0%, #f8fafc 40%, #eef2ff 100%)",
  padding: "28px 16px",
  boxSizing: "border-box",
};

const containerStyle: React.CSSProperties = {
  maxWidth: "1200px",
  margin: "0 auto",
};

const topBarStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  marginBottom: "16px",
  flexWrap: "wrap",
};

const titleStyle: React.CSSProperties = {
  margin: 0,
  fontSize: "1.55rem",
  color: "#0f172a",
};

const subtitleStyle: React.CSSProperties = {
  margin: "6px 0 0",
  color: "#475569",
  fontSize: "0.95rem",
};

const loadingBoxStyle: React.CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "12px",
  padding: "14px 16px",
  color: "#334155",
  fontSize: "0.94rem",
};

const RequireTeacherAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { ready, isAuthenticated } = useTeacherAuth();
  if (!ready) {
    return <div style={loadingBoxStyle}>正在恢复教师会话...</div>;
  }
  if (!isAuthenticated) {
    return <Navigate to="/teacher/login" replace />;
  }
  return <>{children}</>;
};

const RequireStudentAuth: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { ready, isAuthenticated } = useStudentAuth();
  const location = useLocation();
  if (!ready) {
    return <div style={loadingBoxStyle}>正在恢复学生会话...</div>;
  }
  if (!isAuthenticated) {
    return <Navigate to={`/student/login${location.search}`} replace />;
  }
  return <>{children}</>;
};

function App() {
  useEffect(() => {
    setBaseUrl(defaultBaseUrl);
  }, []);

  return (
    <div style={pageStyle}>
      <div style={containerStyle}>
        <header style={topBarStyle}>
          <div>
            <h1 style={titleStyle}>Math Homework Auto-Grading</h1>
            <p style={subtitleStyle}>
              通用数学作业批改平台：老师管理班级与作业，学生登录后提交 PDF。
            </p>
          </div>
        </header>

        <Routes>
          <Route path="/" element={<Navigate to="/teacher/login" replace />} />
          <Route path="/teacher/login" element={<TeacherLoginPage />} />
          <Route
            path="/teacher"
            element={
              <RequireTeacherAuth>
                <TeacherDashboard />
              </RequireTeacherAuth>
            }
          />
          <Route path="/teacher/dashboard" element={<Navigate to="/teacher" replace />} />

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
      </div>
    </div>
  );
}

export default App;
