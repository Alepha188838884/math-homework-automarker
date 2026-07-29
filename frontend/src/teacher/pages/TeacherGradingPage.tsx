import React, { useState } from "react";
import FileUploadArea from "../../components/FileUploadArea";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { formatDateTime, getFailureReason, isAnswerFile } from "../../utils";

function TeacherGradingPage() {
  const {
    selectedAssignmentId, latestSolution, gradeAllSummary,
    solutionMessage, actionMessage, isUploadingSolution, isGradingAll,
    uploadSolutionFile, gradeAllSelectedAssignment,
  } = useTeacherWorkspace();

  const [solutionFiles, setSolutionFiles] = useState<File[]>([]);
  const [solutionAreaKey, setSolutionAreaKey] = useState(0);

  const handleUploadSolution = async () => {
    if (selectedAssignmentId === null || solutionFiles.length === 0) return;
    if (!isAnswerFile(solutionFiles[0])) return;
    try {
      await uploadSolutionFile(solutionFiles[0]);
      setSolutionFiles([]);
      setSolutionAreaKey((v) => v + 1);
    } catch { /* Error displayed via solutionMessage */ }
  };

  return (
    <div className="page-stack">
      <section className="card">
        <h2 className="section-title">批改中心</h2>
        <FileUploadArea key={`solution-area-${solutionAreaKey}`} label="官方答案文件（DOCX / PDF）" accept=".docx,.pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf" multiple={false} onFilesSelected={setSolutionFiles} />
        <div style={{ marginTop: "14px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button type="button" onClick={() => void handleUploadSolution()} disabled={isUploadingSolution || selectedAssignmentId === null || solutionFiles.length === 0 || !isAnswerFile(solutionFiles[0])} className="btn btn-primary">
            {isUploadingSolution ? "上传中..." : "上传官方答案"}
          </button>
          <button type="button" onClick={() => void gradeAllSelectedAssignment()} disabled={isGradingAll || selectedAssignmentId === null} className="btn btn-secondary">
            {isGradingAll ? "批量批改中..." : "批量批改全部提交"}
          </button>
        </div>

        {selectedAssignmentId === null && <div className="empty-state" style={{ marginTop: "14px" }}>请先在顶部选择作业后再上传官方答案或发起批改。</div>}
        {solutionFiles.length > 0 && !isAnswerFile(solutionFiles[0]) && <div className="alert alert-error" style={{ marginTop: "12px" }}>官方答案必须是 .docx 或 .pdf 文件。</div>}
        {solutionMessage && <div className={`alert alert-${solutionMessage.type}`} style={{ marginTop: "12px" }}>{solutionMessage.text}</div>}
        {actionMessage && <div className={`alert alert-${actionMessage.type}`} style={{ marginTop: "12px" }}>{actionMessage.text}</div>}
        {latestSolution && (
          <div className="debug-info">
            <div><strong>答案文件：</strong> {latestSolution.original_filename}</div>
            <div><strong>上传时间：</strong> {formatDateTime(latestSolution.uploaded_at)}</div>
          </div>
        )}
        {gradeAllSummary && (
          <div className="summary-panel">
            <div className="summary-grid">
              <div><strong>总计:</strong> {gradeAllSummary.total}</div>
              <div><strong>已批改:</strong> {gradeAllSummary.graded}</div>
              <div><strong>失败:</strong> {gradeAllSummary.failed}</div>
              <div><strong>跳过:</strong> {gradeAllSummary.skipped}</div>
            </div>
            {gradeAllSummary.failures.length > 0 && (
              <div style={{ marginTop: "10px" }}>
                <strong>失败详情:</strong>
                <ul style={{ margin: "8px 0 0", paddingLeft: "20px" }}>
                  {gradeAllSummary.failures.map((f) => <li key={f.submission_id}>#{f.submission_id}: {getFailureReason(f)}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </section>
    </div>
  );
}

export default TeacherGradingPage;
