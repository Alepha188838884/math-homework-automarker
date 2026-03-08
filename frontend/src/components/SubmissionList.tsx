import React from "react";
import type { Submission } from "../api";

export interface SubmissionListProps {
  submissions: Submission[];
  gradingIds: Set<number>;
  viewingIds: Set<number>;
  onGrade: (submissionId: number) => Promise<void> | void;
  onViewResult: (submissionId: number) => Promise<void> | void;
}

function statusColor(status: string): string {
  if (status === "graded") return "#16a34a";
  if (status === "needs_manual_review") return "#d97706";
  if (status === "grading") return "#2563eb";
  if (status.startsWith("failed")) return "#dc2626";
  return "#64748b";
}

function SubmissionList({
  submissions,
  gradingIds,
  viewingIds,
  onGrade,
  onViewResult,
}: SubmissionListProps) {
  if (submissions.length === 0) {
    return (
      <div
        style={{
          border: "1px dashed #cbd5e1",
          borderRadius: "10px",
          padding: "16px",
          color: "#64748b",
          backgroundColor: "#f8fafc",
        }}
      >
        当前作业暂无提交记录（来自后端数据）。
      </div>
    );
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          backgroundColor: "#fff",
          border: "1px solid #e2e8f0",
          borderRadius: "10px",
          overflow: "hidden",
        }}
      >
        <thead style={{ backgroundColor: "#f1f5f9" }}>
          <tr>
            <th style={thStyle}>Submission ID</th>
            <th style={thStyle}>Student ID</th>
            <th style={thStyle}>Filename</th>
            <th style={thStyle}>Status</th>
            <th style={thStyle}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {submissions.map((submission) => {
            const isGrading = gradingIds.has(submission.id);
            const isViewing = viewingIds.has(submission.id);

            return (
              <tr key={submission.id}>
                <td style={tdStyle}>{submission.id}</td>
                <td style={tdStyle}>{submission.student_id}</td>
                <td style={tdStyle}>{submission.original_filename}</td>
                <td style={tdStyle}>
                  <span
                    style={{
                      padding: "4px 8px",
                      borderRadius: "999px",
                      backgroundColor: `${statusColor(submission.status)}20`,
                      color: statusColor(submission.status),
                      fontWeight: 600,
                      fontSize: "0.86rem",
                    }}
                  >
                    {submission.status}
                  </span>
                </td>
                <td style={{ ...tdStyle, minWidth: "240px" }}>
                  <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                    <button
                      type="button"
                      onClick={() => onGrade(submission.id)}
                      disabled={isGrading}
                      style={primaryButtonStyle}
                    >
                      {isGrading ? "Grading..." : "Grade this submission"}
                    </button>
                    <button
                      type="button"
                      onClick={() => onViewResult(submission.id)}
                      disabled={isViewing}
                      style={secondaryButtonStyle}
                    >
                      {isViewing ? "Loading..." : "View result"}
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

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "12px",
  fontSize: "0.9rem",
  color: "#334155",
  borderBottom: "1px solid #e2e8f0",
};

const tdStyle: React.CSSProperties = {
  padding: "12px",
  borderBottom: "1px solid #e2e8f0",
  color: "#0f172a",
  fontSize: "0.95rem",
  verticalAlign: "top",
};

const primaryButtonStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  padding: "8px 10px",
  backgroundColor: "#2563eb",
  color: "#fff",
  cursor: "pointer",
};

const secondaryButtonStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  padding: "8px 10px",
  backgroundColor: "#fff",
  color: "#0f172a",
  cursor: "pointer",
};

export default SubmissionList;
