import React, { useEffect, useState } from "react";
import type { GradeResult, GradeQuestion } from "../api";

export interface GradeResultModalProps {
  isOpen: boolean;
  result: GradeResult | null;
  onClose: () => void;
  editable?: boolean;
  onSaveQuestion?: (
    questionNumber: number,
    payload: { score: number; is_correct: boolean; comment?: string },
  ) => Promise<void>;
}

function GradeResultModal({ isOpen, result, onClose, editable, onSaveQuestion }: GradeResultModalProps) {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  const [editingNumber, setEditingNumber] = useState<number | null>(null);
  const [draftScore, setDraftScore] = useState<string>("");
  const [draftIsCorrect, setDraftIsCorrect] = useState<boolean>(false);
  const [draftComment, setDraftComment] = useState<string>("");
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setEditingNumber(null);
    setSaveError(null);
  }, [result?.submission_id, isOpen]);

  if (!isOpen || !result) return null;

  const isManualReview = result.status === "needs_manual_review";

  const handleEdit = (q: GradeQuestion) => {
    setEditingNumber(q.number);
    setDraftScore(String(q.score ?? 0));
    setDraftIsCorrect(q.is_correct ?? false);
    setDraftComment(q.comment ?? "");
    setSaveError(null);
  };

  const handleCancel = () => {
    setEditingNumber(null);
    setSaveError(null);
  };

  const handleSave = async (q: GradeQuestion) => {
    const parsed = Number(draftScore);
    if (!Number.isFinite(parsed) || parsed < 0 || parsed > q.max_score) {
      setSaveError("分数必须在 0 到 " + q.max_score + " 之间。");
      return;
    }
    if (onSaveQuestion) {
      setIsSaving(true);
      setSaveError(null);
      try {
        await onSaveQuestion(q.number, { score: parsed, is_correct: draftIsCorrect, comment: draftComment.trim() });
        setEditingNumber(null);
      } catch (error) {
        setSaveError(error instanceof Error ? error.message : "保存失败，请重试。");
      } finally {
        setIsSaving(false);
      }
    }
  };

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
                {editable && <th>操作</th>}
              </tr>
            </thead>
            <tbody>
              {result.questions.map((q) => {
                const isEditing = q.number === editingNumber;
                return (
                  <tr key={`${result.submission_id}-${q.number}`}>
                    <td>{q.number}</td>
                    {isEditing ? (
                      <td>
                        <select className="form-input" value={draftIsCorrect ? "true" : "false"} onChange={(e) => setDraftIsCorrect(e.target.value === "true")}>
                          <option value="true">正确</option>
                          <option value="false">错误</option>
                        </select>
                      </td>
                    ) : (
                      <td>{q.is_correct === null ? "待复核" : q.is_correct ? "正确" : "错误"}</td>
                    )}
                    {isEditing ? (
                      <td>
                        <input
                          type="number"
                          className="form-input"
                          style={{ width: "72px" }}
                          min={0}
                          max={q.max_score}
                          step="0.5"
                          value={draftScore}
                          onChange={(e) => setDraftScore(e.target.value)}
                        />
                      </td>
                    ) : (
                      <td>{q.score === null ? "-" : q.score}</td>
                    )}
                    <td>{q.max_score}</td>
                    {isEditing ? (
                      <td>
                        <input
                          type="text"
                          className="form-input"
                          style={{ minWidth: 0 }}
                          value={draftComment}
                          onChange={(e) => setDraftComment(e.target.value)}
                        />
                      </td>
                    ) : (
                      <td>{q.comment ?? "-"}</td>
                    )}
                    {editable && (
                      <td>
                        {isEditing ? (
                          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                            <button type="button" className="btn btn-primary" disabled={isSaving} onClick={() => handleSave(q)}>保存</button>
                            <button type="button" className="btn btn-secondary" disabled={isSaving} onClick={handleCancel}>取消</button>
                          </div>
                        ) : (
                          <button type="button" className="btn btn-secondary" onClick={() => handleEdit(q)}>修改</button>
                        )}
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {editable && saveError && <div className="alert alert-error" style={{ marginTop: "8px" }}>{saveError}</div>}

        <div style={{ marginTop: "20px", textAlign: "right" }}>
          <button type="button" onClick={onClose} className="btn btn-primary">关闭</button>
        </div>
      </div>
    </div>
  );
}

export default GradeResultModal;
