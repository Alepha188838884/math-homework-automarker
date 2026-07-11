import React, { useEffect } from "react";
import type { GradeResult } from "../api";

export interface GradeResultModalProps {
  isOpen: boolean;
  result: GradeResult | null;
  onClose: () => void;
}

function GradeResultModal({ isOpen, result, onClose }: GradeResultModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !result) return null;

  const isManualReview = result.status === "needs_manual_review";

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="批改结果">
        <div className="modal-header">
          <h3 className="modal-title">提交 #{result.submission_id} 批改结果</h3>
          <button type="button" onClick={onClose} className="modal-close" aria-label="关闭">×</button>
        </div>

        <div className="score-display">
          <strong>{isManualReview ? "自动评分小计" : "总分"}:</strong> {result.total_score} / {result.max_total_score}
          {isManualReview ? "（仍需人工复核）" : ""}
        </div>

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>题号</th>
                <th>正确</th>
                <th>得分</th>
                <th>满分</th>
                <th>评语</th>
              </tr>
            </thead>
            <tbody>
              {result.questions.map((q) => (
                <tr key={`${result.submission_id}-${q.number}`}>
                  <td>{q.number}</td>
                  <td>{q.is_correct === null ? "待复核" : q.is_correct ? "正确" : "错误"}</td>
                  <td>{q.score === null ? "-" : q.score}</td>
                  <td>{q.max_score}</td>
                  <td>{q.comment ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div style={{ marginTop: "20px", textAlign: "right" }}>
          <button type="button" onClick={onClose} className="btn btn-primary">关闭</button>
        </div>
      </div>
    </div>
  );
}

export default GradeResultModal;
