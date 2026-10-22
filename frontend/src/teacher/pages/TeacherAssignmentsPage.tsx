import React, { useState } from "react";
import { createAssignment } from "../../api";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { formatDateTime, getErrorMessage, type StatusMessage } from "../../utils";

function TeacherAssignmentsPage() {
  const {
    selectedCourseId, selectedAssignmentId, setSelectedAssignmentId,
    courseAssignments, assignmentsError, isLoadingAssignments, loadAssignmentsForCourse,
    deleteAssignmentById, actionMessage,
  } = useTeacherWorkspace();

  const [title, setTitle] = useState("");
  const [desc, setDesc] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);

  const handleCreate = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage(null);
    if (selectedCourseId === null) { setMessage({ type: "error", text: "请先选择班级。" }); return; }
    try {
      setIsCreating(true);
      // datetime-local has no timezone; interpret the entered wall-clock time as Asia/Shanghai (UTC+8).
      const due = dueDate.trim() ? new Date(`${dueDate}:00+08:00`).toISOString() : undefined;
      let ms: number | undefined;
      if (maxScore.trim()) {
        const p = Number(maxScore);
        if (!Number.isFinite(p) || p <= 0) { setMessage({ type: "error", text: "max_score 必须是正数。" }); return; }
        ms = p;
      }
      const a = await createAssignment(selectedCourseId, { title: title.trim(), description: desc.trim() || undefined, due_date: due, max_score: ms });
      await loadAssignmentsForCourse(selectedCourseId);
      setSelectedAssignmentId(a.id);
      setTitle(""); setDesc(""); setDueDate(""); setMaxScore("");
      setMessage({ type: "success", text: "作业创建成功。" });
    } catch (error) { setMessage({ type: "error", text: getErrorMessage(error) }); }
    finally { setIsCreating(false); }
  };

  const handleDeleteAssignment = (assignmentId: number) => {
    if (window.confirm("删除作业将同时删除全部提交与批改结果，且不可恢复。确定删除？")) {
      void deleteAssignmentById(assignmentId);
    }
  };

  return (
    <div className="page-stack">
      <section className="card">
        <div className="header-row">
          <h2 className="section-title">作业管理</h2>
          <button type="button" className="btn btn-secondary" disabled={isLoadingAssignments || selectedCourseId === null}
            onClick={() => { if (selectedCourseId !== null) void loadAssignmentsForCourse(selectedCourseId); }}>
            {isLoadingAssignments ? "加载中..." : "刷新作业"}
          </button>
        </div>

        <div className="split-grid">
          <div>
            <h3 className="sub-title">当前班级作业</h3>
            {selectedCourseId === null ? (
              <div className="empty-state">请先在顶部选择班级</div>
            ) : (
              <>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "12px" }}>
                  <select className="form-input" style={{ minWidth: "min(280px, 100%)" }} value={selectedAssignmentId ?? ""}
                    onChange={(e) => { const v = Number(e.target.value); setSelectedAssignmentId(Number.isFinite(v) && v > 0 ? v : null); }}
                    disabled={isLoadingAssignments || courseAssignments.length === 0}>
                    {courseAssignments.length === 0 ? <option value="">暂无作业</option> :
                      courseAssignments.map((a) => <option key={a.id} value={a.id}>#{a.id} - {a.title}</option>)}
                  </select>
                </div>
                {courseAssignments.length === 0 ? (
                  <div className="empty-state">当前班级暂无作业。</div>
                ) : (
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead><tr><th>ID</th><th>标题</th><th>截止日期</th><th>满分</th><th>创建时间</th><th>操作</th></tr></thead>
                      <tbody>
                        {courseAssignments.map((a) => (
                          <tr key={a.id}>
                            <td>{a.id}</td><td>{a.title}</td><td>{formatDateTime(a.due_date)}</td><td>{a.max_score ?? "-"}</td><td>{formatDateTime(a.created_at)}</td>
                            <td><button type="button" className="btn btn-danger" onClick={() => handleDeleteAssignment(a.id)}>删除</button></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {selectedAssignmentId && <div className="inline-info" style={{ marginTop: "12px" }}>当前作业提交状态会每 10 秒自动刷新。</div>}
              </>
            )}
            {assignmentsError && <div className="alert alert-error" style={{ marginTop: "12px" }}>{assignmentsError}</div>}
          </div>
          <div>
            <h3 className="sub-title">创建作业</h3>
            <form onSubmit={handleCreate} className="form-stack">
              <label className="form-group"><span className="form-label">标题</span><input className="form-input" value={title} onChange={(e) => setTitle(e.target.value)} required /></label>
              <label className="form-group"><span className="form-label">描述（可选）</span><input className="form-input" value={desc} onChange={(e) => setDesc(e.target.value)} /></label>
              <label className="form-group"><span className="form-label">截止日期（可选）</span><input className="form-input" type="datetime-local" value={dueDate} onChange={(e) => setDueDate(e.target.value)} /></label>
              <label className="form-group"><span className="form-label">满分（可选）</span><input className="form-input" type="number" min="0" step="0.5" placeholder="默认 100" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} /></label>
              <button type="submit" className="btn btn-primary" disabled={isCreating}>{isCreating ? "创建中..." : "创建作业"}</button>
            </form>
          </div>
        </div>
        {message && <div className={`alert alert-${message.type}`} style={{ marginTop: "12px" }}>{message.text}</div>}
        {actionMessage && <div className={`alert alert-${actionMessage.type}`} style={{ marginTop: "12px" }}>{actionMessage.text}</div>}
      </section>
    </div>
  );
}

export default TeacherAssignmentsPage;
