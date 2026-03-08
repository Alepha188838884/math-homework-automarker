import React from "react";
import type { GradeResult } from "../api";

export interface GradeResultModalProps {
  isOpen: boolean;
  result: GradeResult | null;
  onClose: () => void;
}

function GradeResultModal({ isOpen, result, onClose }: GradeResultModalProps) {
  if (!isOpen || !result) {
    return null;
  }

  const isManualReview = result.status === "needs_manual_review";

  return (
    <div style={overlayStyle} onClick={onClose}>
      <div
        style={modalStyle}
        onClick={(event) => event.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Grade Result"
      >
        <div style={headerStyle}>
          <h3 style={{ margin: 0 }}>Submission #{result.submission_id} 批改结果</h3>
          <button type="button" onClick={onClose} style={closeButtonStyle}>
            ×
          </button>
        </div>

        <div style={scoreStyle}>
          <strong>{isManualReview ? "自动评分小计" : "总分"}:</strong> {result.total_score} /{" "}
          {result.max_total_score}
          {isManualReview ? "（仍需人工复核）" : ""}
        </div>

        <div style={{ overflowX: "auto" }}>
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Question</th>
                <th style={thStyle}>Is Correct</th>
                <th style={thStyle}>Score</th>
                <th style={thStyle}>Max Score</th>
                <th style={thStyle}>Comment</th>
              </tr>
            </thead>
            <tbody>
              {result.questions.map((q) => (
                <tr key={`${result.submission_id}-${q.number}`}>
                  <td style={tdStyle}>{q.number}</td>
                  <td style={tdStyle}>
                    {q.is_correct === null ? "待复核" : q.is_correct ? "Yes" : "No"}
                  </td>
                  <td style={tdStyle}>{q.score === null ? "-" : q.score}</td>
                  <td style={tdStyle}>{q.max_score}</td>
                  <td style={tdStyle}>{q.comment ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: "16px", textAlign: "right" }}>
          <button type="button" onClick={onClose} style={footerCloseButtonStyle}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: "fixed",
  inset: 0,
  backgroundColor: "rgba(15, 23, 42, 0.5)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "16px",
  zIndex: 999,
};

const modalStyle: React.CSSProperties = {
  width: "100%",
  maxWidth: "900px",
  maxHeight: "90vh",
  overflow: "auto",
  backgroundColor: "#ffffff",
  borderRadius: "12px",
  padding: "18px",
  boxShadow: "0 20px 40px rgba(15, 23, 42, 0.2)",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: "12px",
};

const closeButtonStyle: React.CSSProperties = {
  border: "none",
  background: "transparent",
  fontSize: "1.4rem",
  lineHeight: 1,
  cursor: "pointer",
};

const scoreStyle: React.CSSProperties = {
  marginBottom: "12px",
  color: "#0f172a",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  border: "1px solid #e2e8f0",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px",
  backgroundColor: "#f8fafc",
  borderBottom: "1px solid #e2e8f0",
  color: "#334155",
  fontSize: "0.9rem",
};

const tdStyle: React.CSSProperties = {
  padding: "10px",
  borderBottom: "1px solid #e2e8f0",
  color: "#0f172a",
  verticalAlign: "top",
};

const footerCloseButtonStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  padding: "8px 12px",
  backgroundColor: "#0f172a",
  color: "#ffffff",
  cursor: "pointer",
};

export default GradeResultModal;
