import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fetchMyAssignmentsOverview, fetchMySubmissionResult, type GradeResult, type StudentAssignmentOverview, uploadSubmissionForMe } from "../api";
import { useStudentAuth } from "../auth/StudentAuthContext";
import { formatDateTime, getErrorMessage, isPdfFile, statusLabels, type StatusMessage } from "../utils";
import FileUploadArea from "./FileUploadArea";
import GradeResultModal from "./GradeResultModal";

function buildStatusText(item: StudentAssignmentOverview): string {
  if (!item.has_submitted) return "未提交";
  if (item.submission_status === "needs_manual_review") {
    if (item.total_score != null && item.max_total_score != null)
      return `待人工复核（自动评分小计 ${item.total_score} / ${item.max_total_score}）`;
    return "待人工复核";
  }
  if (item.total_score != null && item.max_total_score != null)
    return `已批改（${item.total_score} / ${item.max_total_score}）`;
  const status = item.submission_status ?? "uploaded";
  if (status === "uploaded") return "已提交";
  if (Object.prototype.hasOwnProperty.call(statusLabels, status)) return statusLabels[status];
  return `已提交（${status}）`;
}

function StudentUploadPage() {
  const navigate = useNavigate();
  const { student, logoutStudent } = useStudentAuth();
  const [assignmentsOverview, setAssignmentsOverview] = useState<StudentAssignmentOverview[]>([]);
  const [activeAssignmentId, setActiveAssignmentId] = useState<number | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadAreaKey, setUploadAreaKey] = useState(0);
  const [isLoadingAssignments, setIsLoadingAssignments] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);
  const [resultModalOpen, setResultModalOpen] = useState(false);
  const [resultData, setResultData] = useState<GradeResult | null>(null);
  const [isLoadingResult, setIsLoadingResult] = useState(false);

  const loadAssignmentsOverview = useCallback(async (preferredId?: number | null) => {
    setIsLoadingAssignments(true);
    try {
      const data = await fetchMyAssignmentsOverview();
      setAssignmentsOverview(data);
      setActiveAssignmentId((prev) => {
        for (const c of [preferredId ?? null, prev, data.find((i) => !i.has_submitted)?.assignment_id ?? null, data[0]?.assignment_id ?? null]) {
          if (typeof c === "number" && data.some((i) => i.assignment_id === c)) return c;
        }
        return null;
      });
    } catch (error) {
      setMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsLoadingAssignments(false);
    }
  }, []);

  useEffect(() => { void loadAssignmentsOverview(); }, [loadAssignmentsOverview]);

  const activeAssignment = useMemo(
    () => assignmentsOverview.find((i) => i.assignment_id === activeAssignmentId) ?? null,
    [assignmentsOverview, activeAssignmentId],
  );

  const handleUpload = async () => {
    setMessage(null);
    try {
      if (activeAssignmentId === null) throw new Error("请先在列表里选择一份作业。");
      if (files.length === 0) throw new Error("请先选择 PDF 文件。");
      if (!isPdfFile(files[0])) throw new Error("仅支持 .pdf 文件。");
      setIsUploading(true);
      await uploadSubmissionForMe(activeAssignmentId, files[0]);
      setMessage({ type: "success", text: "上传成功，请等待老师批改。" });
      setFiles([]);
      setUploadAreaKey((v) => v + 1);
      await loadAssignmentsOverview(activeAssignmentId);
    } catch (error) {
      setMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsUploading(false);
    }
  };

  const handleViewResult = async (submissionId: number) => {
    setMessage(null);
    setIsLoadingResult(true);
    try {
      const data = await fetchMySubmissionResult(submissionId);
      setResultData(data);
      setResultModalOpen(true);
    } catch (error) {
      setMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsLoadingResult(false);
    }
  };

  return (
    <>
    <section className="card">
      <div className="workspace-header">
        <div>
          <h2 className="section-title" style={{ marginBottom: "8px" }}>作业任务列表</h2>
          <p className="hint" style={{ marginBottom: "4px" }}>任意题型均可上传，系统会根据老师的官方标准解答进行统一批改。</p>
          {student && <p className="context-hint">当前学生：{student.name}（{student.email}）</p>}
        </div>
        <button type="button" className="btn btn-secondary" onClick={() => { logoutStudent(); navigate("/student/login", { replace: true }); }}>
          退出登录
        </button>
      </div>

      <div style={{ marginTop: "14px" }}>
        <button type="button" className="btn btn-secondary" onClick={() => void loadAssignmentsOverview(activeAssignmentId)} disabled={isLoadingAssignments}>
          {isLoadingAssignments ? "加载中..." : "刷新作业列表"}
        </button>
      </div>

      <div style={{ marginTop: "14px" }}>
        {assignmentsOverview.length === 0 ? (
          isLoadingAssignments ? (
            <div className="alert alert-info">正在加载作业列表...</div>
          ) : (
            <div className="alert alert-info">当前没有可提交的作业，请联系老师发布作业后再试。</div>
          )
        ) : (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>标题</th>
                  <th>描述</th>
                  <th>截止日期</th>
                  <th>创建时间</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {assignmentsOverview.map((item) => (
                  <tr key={item.assignment_id} className={item.assignment_id === activeAssignmentId ? "row-active" : ""}>
                    <td>{item.title}</td>
                    <td>{item.description ?? "-"}</td>
                    <td>{formatDateTime(item.due_date)}</td>
                    <td>{formatDateTime(item.created_at)}</td>
                    <td>{buildStatusText(item)}</td>
                    <td>
                      <div style={{ display: "flex", gap: "8px", flexWrap: "wrap" }}>
                        <button type="button" className="btn btn-primary" onClick={() => { setActiveAssignmentId(item.assignment_id); setMessage(null); }}>
                          {item.has_submitted ? "重新提交" : "提交作业"}
                        </button>
                        {(item.submission_status === "graded" || item.submission_status === "needs_manual_review") && item.submission_id && (
                          <button type="button" className="btn btn-secondary" disabled={isLoadingResult} onClick={() => void handleViewResult(item.submission_id!)}>
                            查看批改详情
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {activeAssignment && (
        <div className="upload-panel">
          <h3 style={{ margin: "0 0 12px", fontSize: "1.02rem", fontWeight: 600 }}>
            当前选择：#{activeAssignment.assignment_id} {activeAssignment.title}
          </h3>
          <FileUploadArea key={`student-upload-${uploadAreaKey}`} label="学生作业 PDF" accept="application/pdf,.pdf" multiple={false} onFilesSelected={setFiles} />
          <div style={{ marginTop: "14px" }}>
            <button type="button" onClick={handleUpload} disabled={isUploading} className="btn btn-primary">
              {isUploading ? "上传中..." : "上传作业"}
            </button>
          </div>
        </div>
      )}

      {message && <div className={`alert alert-${message.type}`} style={{ marginTop: "14px" }}>{message.text}</div>}
    </section>
    <GradeResultModal isOpen={resultModalOpen} result={resultData} onClose={() => setResultModalOpen(false)} />
    </>
  );
}

export default StudentUploadPage;
