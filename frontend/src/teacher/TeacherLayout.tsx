import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTeacherAuth } from "../auth/TeacherAuthContext";
import { useTeacherWorkspace } from "./TeacherWorkspaceContext";

const navItems = [
  { to: "/teacher/courses", label: "班级管理" },
  { to: "/teacher/students", label: "学生管理" },
  { to: "/teacher/assignments", label: "作业管理" },
  { to: "/teacher/grading", label: "批改中心" },
  { to: "/teacher/submission-status", label: "提交状态" },
  { to: "/teacher/submission-records", label: "提交记录" },
];

function TeacherLayout() {
  const navigate = useNavigate();
  const { teacher, logoutTeacher } = useTeacherAuth();
  const {
    courses, selectedCourseId, selectedAssignmentId,
    courseAssignments, isLoadingAssignments,
    setSelectedCourseId, setSelectedAssignmentId,
  } = useTeacherWorkspace();

  return (
    <div className="layout-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="sidebar-icon">数</div>
          <h2 className="sidebar-title">教师后台</h2>
        </div>
        <p className="sidebar-hint">管理班级、学生、作业与批改</p>

        <nav className="nav-list" aria-label="教师后台导航">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="content-shell">
        <section className="workspace-bar">
          <div className="workspace-header">
            <div>
              <h2 className="workspace-title">教师工作台</h2>
              <p className="workspace-subtitle">{teacher ? `${teacher.name}（${teacher.email}）` : "未知教师"}</p>
            </div>
            <div className="workspace-actions">
              <button type="button" className="btn btn-secondary" onClick={() => { logoutTeacher(); navigate("/teacher/login", { replace: true }); }}>
                退出登录
              </button>
            </div>
          </div>

          <div className="selector-grid">
            <label className="form-group">
              <span className="form-label">当前班级</span>
              <select
                className="form-input"
                value={selectedCourseId ?? ""}
                onChange={(e) => { const v = Number(e.target.value); setSelectedCourseId(Number.isFinite(v) && v > 0 ? v : null); }}
                disabled={courses.length === 0}
              >
                {courses.length === 0 ? (
                  <option value="">暂无班级</option>
                ) : courses.map((c) => (
                  <option key={c.id} value={c.id}>#{c.id} - {c.name}</option>
                ))}
              </select>
            </label>
            <label className="form-group">
              <span className="form-label">当前作业</span>
              <select
                className="form-input"
                value={selectedAssignmentId ?? ""}
                onChange={(e) => { const v = Number(e.target.value); setSelectedAssignmentId(Number.isFinite(v) && v > 0 ? v : null); }}
                disabled={selectedCourseId === null || isLoadingAssignments || courseAssignments.length === 0}
              >
                {selectedCourseId === null ? (
                  <option value="">请先选择班级</option>
                ) : courseAssignments.length === 0 ? (
                  <option value="">{isLoadingAssignments ? "加载中..." : "暂无作业"}</option>
                ) : courseAssignments.map((a) => (
                  <option key={a.id} value={a.id}>#{a.id} - {a.title}</option>
                ))}
              </select>
            </label>
          </div>

          <p className="context-hint" style={{ marginTop: "12px" }}>
            页面切换时会保留当前后端地址、班级选择和作业选择。
          </p>
        </section>

        <Outlet />
      </div>
    </div>
  );
}

export default TeacherLayout;
