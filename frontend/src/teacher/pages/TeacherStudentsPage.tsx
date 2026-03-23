import React, { useState } from "react";
import { createStudent } from "../../api";
import {
  alertBaseStyle,
  buttonPrimaryStyle,
  buttonSecondaryStyle,
  cardStyle,
  emptyBoxStyle,
  fieldStyle,
  formStyle,
  headerRowStyle,
  inputStyle,
  labelTextStyle,
  messageStyle,
  pageStackStyle,
  sectionTitleStyle,
  splitGridStyle,
  subTitleStyle,
  tableStyle,
  tdStyle,
  thStyle,
} from "../styles";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { getErrorMessage, type StatusMessage } from "../utils";


function TeacherStudentsPage() {
  const {
    selectedCourseId,
    courseStudents,
    courseStudentsError,
    isLoadingCourseStudents,
    loadCourseStudents,
  } = useTeacherWorkspace();

  const [showAdvancedStudentTools, setShowAdvancedStudentTools] = useState<boolean>(false);
  const [newStudentName, setNewStudentName] = useState<string>("");
  const [newStudentEmail, setNewStudentEmail] = useState<string>("");
  const [newStudentPassword, setNewStudentPassword] = useState<string>("");
  const [isCreatingStudent, setIsCreatingStudent] = useState<boolean>(false);
  const [studentMessage, setStudentMessage] = useState<StatusMessage | null>(null);

  const handleCreateStudent = async (event: React.FormEvent) => {
    event.preventDefault();
    setStudentMessage(null);
    if (selectedCourseId === null) {
      setStudentMessage({ type: "error", text: "请先选择班级。" });
      return;
    }
    try {
      setIsCreatingStudent(true);
      await createStudent(
        selectedCourseId,
        newStudentName.trim(),
        newStudentEmail.trim(),
        newStudentPassword,
      );
      await loadCourseStudents(selectedCourseId);
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

  return (
    <div style={pageStackStyle}>
      <section style={cardStyle}>
        <div style={headerRowStyle}>
          <h2 style={sectionTitleStyle}>学生管理</h2>
          <button
            type="button"
            style={buttonSecondaryStyle}
            disabled={selectedCourseId === null || isLoadingCourseStudents}
            onClick={() => {
              if (selectedCourseId !== null) {
                void loadCourseStudents(selectedCourseId);
              }
            }}
          >
            {isLoadingCourseStudents ? "Loading..." : "Refresh students"}
          </button>
        </div>

        {selectedCourseId === null ? (
          <div style={emptyBoxStyle}>请先在顶部选择班级</div>
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
              {courseStudentsError && (
                <div style={{ ...alertBaseStyle, ...messageStyle("error") }}>
                  {courseStudentsError}
                </div>
              )}
            </div>

            <div>
              <h3 style={subTitleStyle}>高级管理</h3>
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
    </div>
  );
}

export default TeacherStudentsPage;
