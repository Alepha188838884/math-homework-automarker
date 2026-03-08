import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  fetchMyAssignmentsOverview,
  type StudentAssignmentOverview,
  uploadSubmissionForMe,
} from "../api";
import { useStudentAuth } from "../auth/StudentAuthContext";
import FileUploadArea from "./FileUploadArea";

type MessageType = "success" | "error" | "info";

interface StatusMessage {
  type: MessageType;
  text: string;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function isPdfFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".pdf");
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString();
}

function messageStyle(type: MessageType): React.CSSProperties {
  if (type === "success") {
    return {
      color: "#166534",
      backgroundColor: "#dcfce7",
      border: "1px solid #86efac",
    };
  }
  if (type === "error") {
    return {
      color: "#991b1b",
      backgroundColor: "#fee2e2",
      border: "1px solid #fca5a5",
    };
  }
  return {
    color: "#1e3a8a",
    backgroundColor: "#dbeafe",
    border: "1px solid #93c5fd",
  };
}

function buildStatusText(item: StudentAssignmentOverview): string {
  if (!item.has_submitted) {
    return "未提交";
  }
  if (item.submission_status === "needs_manual_review") {
    if (
      item.total_score !== null &&
      item.total_score !== undefined &&
      item.max_total_score !== null &&
      item.max_total_score !== undefined
    ) {
      return `待人工复核（自动评分小计 ${item.total_score} / ${item.max_total_score}）`;
    }
    return "待人工复核";
  }
  if (
    item.total_score !== null &&
    item.total_score !== undefined &&
    item.max_total_score !== null &&
    item.max_total_score !== undefined
  ) {
    return `已批改（${item.total_score} / ${item.max_total_score}）`;
  }
  const status = item.submission_status ?? "uploaded";
  if (status.startsWith("failed")) {
    return `失败（${status}）`;
  }
  return `已提交（${status}）`;
}

function StudentUploadPage() {
  const navigate = useNavigate();
  const { student, logoutStudent } = useStudentAuth();

  const [assignmentsOverview, setAssignmentsOverview] = useState<StudentAssignmentOverview[]>([]);
  const [activeAssignmentId, setActiveAssignmentId] = useState<number | null>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [uploadAreaKey, setUploadAreaKey] = useState<number>(0);
  const [isLoadingAssignments, setIsLoadingAssignments] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);

  const loadAssignmentsOverview = useCallback(
    async (preferredAssignmentId?: number | null) => {
      setIsLoadingAssignments(true);
      try {
        const data = await fetchMyAssignmentsOverview();
        setAssignmentsOverview(data);
        setActiveAssignmentId((prev) => {
          const candidates = [
            preferredAssignmentId ?? null,
            prev,
            data.find((item) => !item.has_submitted)?.assignment_id ?? null,
            data[0]?.assignment_id ?? null,
          ];
          for (const candidate of candidates) {
            if (
              typeof candidate === "number" &&
              data.some((item) => item.assignment_id === candidate)
            ) {
              return candidate;
            }
          }
          return null;
        });
      } catch (error) {
        setMessage({ type: "error", text: getErrorMessage(error) });
      } finally {
        setIsLoadingAssignments(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadAssignmentsOverview();
  }, [loadAssignmentsOverview]);

  const activeAssignment = useMemo(
    () => assignmentsOverview.find((item) => item.assignment_id === activeAssignmentId) ?? null,
    [assignmentsOverview, activeAssignmentId],
  );

  const handleUpload = async () => {
    setMessage(null);
    try {
      if (activeAssignmentId === null) {
        throw new Error("请先在列表里选择一份作业。");
      }
      if (files.length === 0) {
        throw new Error("请先选择 PDF 文件。");
      }
      const file = files[0];
      if (!isPdfFile(file)) {
        throw new Error("仅支持 .pdf 文件。");
      }

      setIsUploading(true);
      await uploadSubmissionForMe(activeAssignmentId, file);
      setMessage({
        type: "success",
        text: "上传成功，请等待老师批改。",
      });
      setFiles([]);
      setUploadAreaKey((value) => value + 1);
      await loadAssignmentsOverview(activeAssignmentId);
    } catch (error) {
      setMessage({
        type: "error",
        text: getErrorMessage(error),
      });
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <section style={cardStyle}>
      <div style={headerStyle}>
        <div>
          <h2 style={sectionTitleStyle}>作业任务列表</h2>
          <p style={hintStyle}>
            任意题型均可上传，系统会根据老师的官方标准解答进行统一批改。
          </p>
          {student && (
            <p style={{ ...hintStyle, marginBottom: 0 }}>
              当前学生：{student.name}（{student.email}）
            </p>
          )}
        </div>
        <button
          type="button"
          style={logoutButtonStyle}
          onClick={() => {
            logoutStudent();
            navigate("/student/login", { replace: true });
          }}
        >
          退出登录
        </button>
      </div>

      <div style={{ marginTop: "10px" }}>
        <button
          type="button"
          style={buttonSecondaryStyle}
          onClick={() => void loadAssignmentsOverview(activeAssignmentId)}
          disabled={isLoadingAssignments}
        >
          {isLoadingAssignments ? "Loading..." : "刷新作业列表"}
        </button>
      </div>

      <div style={{ marginTop: "12px", overflowX: "auto" }}>
        {assignmentsOverview.length === 0 ? (
          <div style={{ ...alertBaseStyle, ...messageStyle("info") }}>
            当前没有可提交的作业，请联系老师发布作业后再试。
          </div>
        ) : (
          <table style={tableStyle}>
            <thead>
              <tr>
                <th style={thStyle}>Title</th>
                <th style={thStyle}>Description</th>
                <th style={thStyle}>Due Date</th>
                <th style={thStyle}>Created At</th>
                <th style={thStyle}>Status</th>
                <th style={thStyle}>Action</th>
              </tr>
            </thead>
            <tbody>
              {assignmentsOverview.map((item) => (
                <tr
                  key={`student-assignment-${item.assignment_id}`}
                  style={
                    item.assignment_id === activeAssignmentId
                      ? { backgroundColor: "#eff6ff" }
                      : undefined
                  }
                >
                  <td style={tdStyle}>{item.title}</td>
                  <td style={tdStyle}>{item.description ?? "-"}</td>
                  <td style={tdStyle}>{formatDateTime(item.due_date)}</td>
                  <td style={tdStyle}>{formatDateTime(item.created_at)}</td>
                  <td style={tdStyle}>{buildStatusText(item)}</td>
                  <td style={tdStyle}>
                    <button
                      type="button"
                      style={buttonPrimaryStyle}
                      onClick={() => {
                        setActiveAssignmentId(item.assignment_id);
                        setMessage(null);
                      }}
                    >
                      {item.has_submitted ? "重新提交" : "提交作业"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {activeAssignment && (
        <div style={uploadPanelStyle}>
          <h3 style={uploadTitleStyle}>
            当前选择：#{activeAssignment.assignment_id} {activeAssignment.title}
          </h3>
          <FileUploadArea
            key={`student-upload-${uploadAreaKey}`}
            label="Student submission PDF"
            accept="application/pdf,.pdf"
            multiple={false}
            onFilesSelected={setFiles}
          />
          <div style={{ marginTop: "12px" }}>
            <button
              type="button"
              onClick={handleUpload}
              disabled={isUploading}
              style={buttonPrimaryStyle}
            >
              {isUploading ? "Uploading..." : "上传作业"}
            </button>
          </div>
        </div>
      )}

      {message && (
        <div style={{ ...alertBaseStyle, ...messageStyle(message.type) }}>{message.text}</div>
      )}
    </section>
  );
}

const cardStyle: React.CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "16px",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
};

const headerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "flex-start",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap",
};

const sectionTitleStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "10px",
  fontSize: "1.25rem",
  color: "#0f172a",
};

const uploadTitleStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "10px",
  fontSize: "1.03rem",
  color: "#0f172a",
};

const hintStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "10px",
  color: "#475569",
  fontSize: "0.92rem",
  lineHeight: 1.5,
};

const buttonPrimaryStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "8px 12px",
  cursor: "pointer",
};

const buttonSecondaryStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  backgroundColor: "#ffffff",
  color: "#0f172a",
  padding: "8px 12px",
  cursor: "pointer",
};

const logoutButtonStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  backgroundColor: "#ffffff",
  color: "#0f172a",
  padding: "8px 12px",
  cursor: "pointer",
};

const alertBaseStyle: React.CSSProperties = {
  marginTop: "10px",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.92rem",
};

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  border: "1px solid #e2e8f0",
  backgroundColor: "#ffffff",
  borderRadius: "10px",
  overflow: "hidden",
};

const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "10px",
  fontSize: "0.9rem",
  color: "#334155",
  borderBottom: "1px solid #e2e8f0",
  backgroundColor: "#f8fafc",
};

const tdStyle: React.CSSProperties = {
  padding: "10px",
  borderBottom: "1px solid #e2e8f0",
  color: "#0f172a",
  verticalAlign: "top",
  fontSize: "0.94rem",
};

const uploadPanelStyle: React.CSSProperties = {
  marginTop: "14px",
  border: "1px solid #dbeafe",
  borderRadius: "10px",
  padding: "12px",
  backgroundColor: "#f8fbff",
};

export default StudentUploadPage;
