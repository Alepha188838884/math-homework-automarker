import React from "react";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { statusLabel } from "../../utils";

function TeacherSubmissionStatusPage() {
  const { selectedAssignmentId, studentsStatus, actionMessage, submissionDataError, isLoadingSubmissionData } = useTeacherWorkspace();

  return (
    <div className="page-stack">
      <section className="card">
        <h2 className="section-title">学生提交状态</h2>
        {selectedAssignmentId === null ? (
          <div className="empty-state">请选择作业后查看状态。</div>
        ) : isLoadingSubmissionData ? (
          <div className="empty-state">加载中...</div>
        ) : studentsStatus.length === 0 ? (
          <div className="empty-state">当前班级暂无学生或暂无状态数据。</div>
        ) : (
          <>
            <div className="inline-info" style={{ marginBottom: "14px" }}>当前作业提交状态会每 10 秒自动刷新。</div>
            <div className="table-wrap">
              <table className="data-table">
                <thead><tr><th>学生姓名</th><th>邮箱</th><th>是否提交</th><th>提交状态</th><th>分数</th></tr></thead>
                <tbody>
                  {studentsStatus.map((item) => (
                    <tr key={item.student_id}>
                      <td>{item.student_name}</td>
                      <td>{item.student_email}</td>
                      <td>{item.has_submitted ? "已提交" : "未提交"}</td>
                      <td>{item.submission_status ? statusLabel(item.submission_status) : "-"}</td>
                      <td>
                        {item.submission_status === "needs_manual_review" && item.total_score !== null && item.max_total_score !== null
                          ? `自动评分小计 ${item.total_score} / ${item.max_total_score}`
                          : item.total_score !== null && item.max_total_score !== null
                            ? `${item.total_score} / ${item.max_total_score}` : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
        {actionMessage && <div className={`alert alert-${actionMessage.type}`} style={{ marginTop: "12px" }}>{actionMessage.text}</div>}
        {submissionDataError && <div className="alert alert-error" style={{ marginTop: "12px" }}>{submissionDataError}</div>}
      </section>
    </div>
  );
}

export default TeacherSubmissionStatusPage;
