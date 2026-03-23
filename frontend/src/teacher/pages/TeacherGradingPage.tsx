import React, { useState } from "react";
import FileUploadArea from "../../components/FileUploadArea";
import {
  alertBaseStyle,
  buttonPrimaryStyle,
  buttonSecondaryStyle,
  cardStyle,
  debugInfoStyle,
  emptyBoxStyle,
  messageStyle,
  pageStackStyle,
  sectionTitleStyle,
  summaryGridStyle,
  summaryPanelStyle,
} from "../styles";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { getFailureReason, isDocxFile } from "../utils";


function TeacherGradingPage() {
  const {
    selectedAssignmentId,
    latestSolution,
    gradeAllSummary,
    solutionMessage,
    actionMessage,
    isUploadingSolution,
    isGradingAll,
    uploadSolutionFile,
    gradeAllSelectedAssignment,
  } = useTeacherWorkspace();

  const [solutionFiles, setSolutionFiles] = useState<File[]>([]);
  const [solutionAreaKey, setSolutionAreaKey] = useState<number>(0);

  const handleUploadSolution = async () => {
    if (selectedAssignmentId === null) {
      return;
    }
    if (solutionFiles.length === 0) {
      return;
    }
    const file = solutionFiles[0];
    if (!isDocxFile(file)) {
      return;
    }
    try {
      await uploadSolutionFile(file);
      setSolutionFiles([]);
      setSolutionAreaKey((value) => value + 1);
    } catch {
    }
  };

  return (
    <div style={pageStackStyle}>
      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>批改中心</h2>
        <FileUploadArea
          key={`solution-area-${solutionAreaKey}`}
          label="Official solution DOCX"
          accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          multiple={false}
          onFilesSelected={setSolutionFiles}
        />
        <div style={{ marginTop: "12px", display: "flex", gap: "10px", flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => void handleUploadSolution()}
            disabled={
              isUploadingSolution ||
              selectedAssignmentId === null ||
              solutionFiles.length === 0 ||
              !isDocxFile(solutionFiles[0])
            }
            style={buttonPrimaryStyle}
          >
            {isUploadingSolution ? "Uploading..." : "Upload Solution"}
          </button>
          <button
            type="button"
            onClick={() => void gradeAllSelectedAssignment()}
            disabled={isGradingAll || selectedAssignmentId === null}
            style={buttonSecondaryStyle}
          >
            {isGradingAll ? "Grading all..." : "Grade all submissions"}
          </button>
        </div>

        {selectedAssignmentId === null && (
          <div style={emptyBoxStyle}>请先在顶部选择作业后再上传官方答案或发起批改。</div>
        )}
        {solutionFiles.length > 0 && !isDocxFile(solutionFiles[0]) && (
          <div style={{ ...alertBaseStyle, ...messageStyle("error") }}>
            官方答案必须是 .docx 文件。
          </div>
        )}
        {solutionMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(solutionMessage.type) }}>
            {solutionMessage.text}
          </div>
        )}
        {actionMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(actionMessage.type) }}>
            {actionMessage.text}
          </div>
        )}
        {latestSolution && (
          <div style={debugInfoStyle}>
            <div>
              <strong>Latest qwen_file_id:</strong> {latestSolution.qwen_file_id}
            </div>
            <div>
              <strong>Uploaded at:</strong> {latestSolution.uploaded_at}
            </div>
          </div>
        )}
        {gradeAllSummary && (
          <div style={summaryPanelStyle}>
            <div style={summaryGridStyle}>
              <div>
                <strong>Total:</strong> {gradeAllSummary.total}
              </div>
              <div>
                <strong>Graded:</strong> {gradeAllSummary.graded}
              </div>
              <div>
                <strong>Failed:</strong> {gradeAllSummary.failed}
              </div>
              <div>
                <strong>Skipped:</strong> {gradeAllSummary.skipped}
              </div>
            </div>
            {gradeAllSummary.failures.length > 0 && (
              <div style={{ marginTop: "10px" }}>
                <strong>Failures:</strong>
                <ul style={{ margin: "8px 0 0", paddingLeft: "20px" }}>
                  {gradeAllSummary.failures.map((failure) => (
                    <li key={`failure-${failure.submission_id}`}>
                      #{failure.submission_id}: {getFailureReason(failure)}
                    </li>
                  ))}
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
