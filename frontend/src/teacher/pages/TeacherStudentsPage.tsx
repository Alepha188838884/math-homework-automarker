import React, { useState } from "react";
import { createStudent } from "../../api";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { getErrorMessage, type StatusMessage } from "../../utils";

function TeacherStudentsPage() {
  const {
    selectedCourseId, courseStudents, courseStudentsError, isLoadingCourseStudents, loadCourseStudents,
    removeStudent, resetStudentPasswordAction, actionMessage,
  } = useTeacherWorkspace();
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [newName, setNewName] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);
    if (selectedCourseId === null) { setMessage({ type: "error", text: "请先选择班级。" }); return; }
    try {
      setIsCreating(true);
      await createStudent(selectedCourseId, newName.trim(), newEmail.trim(), newPassword);
      await loadCourseStudents(selectedCourseId);
      setNewName(""); setNewEmail(""); setNewPassword("");
      setMessage({ type: "success", text: "学生已添加。" });
    } catch (error) { setMessage({ type: "error", text: getErrorMessage(error) }); }
    finally { setIsCreating(false); }
  };

  const handleRemoveStudent = (studentId: number) => {
    if (selectedCourseId === null) return;
    if (window.confirm("移除该学生将同时删除其全部提交记录，且不可恢复。确定移除？")) {
      void removeStudent(selectedCourseId, studentId);
    }
  };

  const handleResetPassword = (studentId: number) => {
    if (selectedCourseId === null) return;
    const newPassword = window.prompt("请输入该学生的新密码：");
    if (newPassword === null) return;
    if (!newPassword.trim()) {
      setMessage({ type: "error", text: "密码不能为空。" });
      return;
    }
    void resetStudentPasswordAction(selectedCourseId, studentId, newPassword);
  };

  return (
    <div className="page-stack">
      <section className="card">
        <div className="header-row">
          <h2 className="section-title">学生管理</h2>
          <button type="button" className="btn btn-secondary" disabled={selectedCourseId === null || isLoadingCourseStudents}
            onClick={() => { if (selectedCourseId !== null) void loadCourseStudents(selectedCourseId); }}>
            {isLoadingCourseStudents ? "加载中..." : "刷新学生列表"}
          </button>
        </div>

        {selectedCourseId === null ? (
          <div className="empty-state">请先在顶部选择班级</div>
        ) : (
          <div className="split-grid">
            <div>
              <h3 className="sub-title">班级学生列表</h3>
              {isLoadingCourseStudents ? (
                <div className="empty-state">加载中...</div>
              ) : courseStudents.length === 0 ? (
                <div className="empty-state">该班级暂无学生</div>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead><tr><th>ID</th><th>姓名</th><th>邮箱</th><th>操作</th></tr></thead>
                    <tbody>
                      {courseStudents.map((s) => (
                        <tr key={s.id}>
                          <td>{s.id}</td><td>{s.name}</td><td>{s.email}</td>
                          <td>
                            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                              <button type="button" className="btn btn-danger" onClick={() => handleRemoveStudent(s.id)}>移除</button>
                              <button type="button" className="btn btn-secondary" onClick={() => handleResetPassword(s.id)}>重置密码</button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {courseStudentsError && <div className="alert alert-error" style={{ marginTop: "12px" }}>{courseStudentsError}</div>}
            </div>
            <div>
              <h3 className="sub-title">高级管理</h3>
              <button type="button" className="btn btn-secondary" onClick={() => setShowAdvanced((p) => !p)}>
                {showAdvanced ? "隐藏手动添加学生" : "显示手动添加学生"}
              </button>
              {showAdvanced && (
                <form onSubmit={handleCreate} className="form-stack" style={{ marginTop: "14px" }}>
                  <label className="form-group"><span className="form-label">姓名</span><input className="form-input" value={newName} onChange={(e) => setNewName(e.target.value)} required /></label>
                  <label className="form-group"><span className="form-label">邮箱</span><input className="form-input" type="email" value={newEmail} onChange={(e) => setNewEmail(e.target.value)} required /></label>
                  <label className="form-group"><span className="form-label">初始密码</span><input className="form-input" type="password" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required /></label>
                  <button type="submit" className="btn btn-primary" disabled={isCreating}>{isCreating ? "创建中..." : "添加学生"}</button>
                </form>
              )}
            </div>
          </div>
        )}
        {message && <div className={`alert alert-${message.type}`} style={{ marginTop: "12px" }}>{message.text}</div>}
        {actionMessage && <div className={`alert alert-${actionMessage.type}`} style={{ marginTop: "12px" }}>{actionMessage.text}</div>}
      </section>
    </div>
  );
}

export default TeacherStudentsPage;
