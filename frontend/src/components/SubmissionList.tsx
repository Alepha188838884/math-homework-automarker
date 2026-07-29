import React from "react";
import type { Submission } from "../api";
import { statusLabel } from "../utils";

export interface SubmissionListProps {
  submissions: Submission[];
  gradingIds: Set<number>;
  viewingIds: Set<number>;
  onGrade: (submissionId: number) => Promise<void> | void;
  onViewResult: (submissionId: number) => Promise<void> | void;
}

function badgeClass(status: string): string {
  if (status === "graded") return "badge badge-graded";
  if (status === "needs_manual_review") return "badge badge-review";
  if (status === "grading") return "badge badge-grading";
  if (status.startsWith("failed")) return "badge badge-failed";
  return "badge badge-uploaded";
}

function SubmissionList({ submissions, gradingIds, viewingIds, onGrade, onViewResult }: SubmissionListProps) {
  if (submissions.length === 0) {
    return <div className="empty-state">当前作业暂无提交记录（来自后端数据）。</div>;
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>提交 ID</th>
            <th>学生 ID</th>
            <th>文件名</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {submissions.map((s) => {
            const isGrading = gradingIds.has(s.id);
            const isViewing = viewingIds.has(s.id);
            const isSubmissionGrading = s.status === "grading";
            return (
              <tr key={s.id}>
                <td>{s.id}</td>
                <td>{s.student_id}</td>
                <td>{s.original_filename}</td>
                <td><span className={badgeClass(s.status)}>{statusLabel(s.status)}</span></td>
                <td>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button type="button" onClick={() => onGrade(s.id)} disabled={isGrading || isSubmissionGrading} className="btn btn-primary">
                      {isGrading ? "批改中..." : isSubmissionGrading ? statusLabel(s.status) : "批改"}
                    </button>
                    <button type="button" onClick={() => onViewResult(s.id)} disabled={isViewing} className="btn btn-secondary">
                      {isViewing ? "加载中..." : "查看结果"}
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default SubmissionList;
