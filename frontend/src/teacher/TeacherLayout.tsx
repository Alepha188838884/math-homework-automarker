import React from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useTeacherAuth } from "../auth/TeacherAuthContext";
import {
  buttonSecondaryStyle,
  contentShellStyle,
  contextHintStyle,
  fieldStyle,
  inputStyle,
  labelTextStyle,
  layoutHeadingStyle,
  layoutShellStyle,
  layoutSubHeadingStyle,
  layoutTopBarStyle,
  layoutTopCardStyle,
  navLinkStyle,
  navListStyle,
  selectorsGridStyle,
  sidebarHintStyle,
  sidebarStyle,
  sidebarTitleStyle,
  topActionsStyle,
} from "./styles";
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
    courses,
    selectedCourseId,
    selectedAssignmentId,
    courseAssignments,
    isLoadingAssignments,
    setSelectedCourseId,
    setSelectedAssignmentId,
  } = useTeacherWorkspace();

  return (
    <div style={layoutShellStyle}>
      <aside style={sidebarStyle}>
        <h2 style={sidebarTitleStyle}>教师后台</h2>
        <p style={sidebarHintStyle}>使用左侧导航切换班级、学生、作业、批改、提交状态和提交记录。</p>

        <nav style={navListStyle} aria-label="教师后台导航">
          {navItems.map((item) => (
            <NavLink key={item.to} to={item.to} style={({ isActive }) => navLinkStyle(isActive)}>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div style={contentShellStyle}>
        <section style={layoutTopCardStyle}>
          <div style={layoutTopBarStyle}>
            <div>
              <h2 style={layoutHeadingStyle}>教师工作台</h2>
              <p style={layoutSubHeadingStyle}>
                {teacher ? `${teacher.name} (${teacher.email})` : "Unknown teacher"}
              </p>
            </div>

            <div style={topActionsStyle}>
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
          </div>

          <div style={selectorsGridStyle}>
            <label style={fieldStyle}>
              <span style={labelTextStyle}>当前班级</span>
              <select
                style={inputStyle}
                value={selectedCourseId ?? ""}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setSelectedCourseId(Number.isFinite(value) && value > 0 ? value : null);
                }}
                disabled={courses.length === 0}
              >
                {courses.length === 0 ? (
                  <option value="">暂无班级</option>
                ) : (
                  courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      #{course.id} - {course.name}
                    </option>
                  ))
                )}
              </select>
            </label>

            <label style={fieldStyle}>
              <span style={labelTextStyle}>当前作业</span>
              <select
                style={inputStyle}
                value={selectedAssignmentId ?? ""}
                onChange={(event) => {
                  const value = Number(event.target.value);
                  setSelectedAssignmentId(Number.isFinite(value) && value > 0 ? value : null);
                }}
                disabled={selectedCourseId === null || isLoadingAssignments || courseAssignments.length === 0}
              >
                {selectedCourseId === null ? (
                  <option value="">请先选择班级</option>
                ) : courseAssignments.length === 0 ? (
                  <option value="">{isLoadingAssignments ? "加载中..." : "暂无作业"}</option>
                ) : (
                  courseAssignments.map((assignment) => (
                    <option key={assignment.id} value={assignment.id}>
                      #{assignment.id} - {assignment.title}
                    </option>
                  ))
                )}
              </select>
            </label>
          </div>

          <p style={{ ...contextHintStyle, marginTop: "12px" }}>
            页面切换时会保留当前 Backend Base URL、班级选择和作业选择。
          </p>
        </section>

        <Outlet />
      </div>
    </div>
  );
}

export default TeacherLayout;
