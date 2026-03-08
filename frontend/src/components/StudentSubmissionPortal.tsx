import React, { useState } from "react";
import { type Submission, uploadSubmission } from "../api";
import FileUploadArea from "./FileUploadArea";

type MessageType = "success" | "error";

interface StatusMessage {
  type: MessageType;
  text: string;
}

interface StudentSubmissionPortalProps {
  assignmentId: string;
  onSubmissionUploaded: (submission: Submission) => void;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function parsePositiveInt(value: string, label: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${label} must be a positive integer.`);
  }
  return parsed;
}

function isPdfFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".pdf");
}

function StudentSubmissionPortal({
  assignmentId,
  onSubmissionUploaded,
}: StudentSubmissionPortalProps) {
  const [studentId, setStudentId] = useState<string>("");
  const [submissionFiles, setSubmissionFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);

  const handleUpload = async () => {
    setMessage(null);
    try {
      const assignment = parsePositiveInt(assignmentId, "assignment_id");
      const student = parsePositiveInt(studentId, "student_id");

      if (submissionFiles.length === 0) {
        throw new Error("Please select at least one PDF submission file.");
      }
      for (const file of submissionFiles) {
        if (!isPdfFile(file)) {
          throw new Error(`File "${file.name}" is not a PDF.`);
        }
      }

      setIsUploading(true);
      let successCount = 0;
      let failedCount = 0;
      const errors: string[] = [];

      for (const file of submissionFiles) {
        try {
          const uploaded = await uploadSubmission(assignment, student, file);
          onSubmissionUploaded(uploaded);
          successCount += 1;
        } catch (error) {
          failedCount += 1;
          errors.push(`${file.name}: ${getErrorMessage(error)}`);
        }
      }

      if (failedCount === 0) {
        setMessage({
          type: "success",
          text: `Uploaded ${successCount} submission(s) successfully.`,
        });
      } else {
        setMessage({
          type: "error",
          text: `Uploaded ${successCount}, failed ${failedCount}. ${errors
            .slice(0, 2)
            .join(" | ")}`,
        });
      }
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
      <h2 style={sectionTitleStyle}>Student Submission Side</h2>
      <p style={hintStyle}>
        学生端只负责上传作业 PDF；上传后会进入老师端当前会话的 submissions 列表。
      </p>

      <div style={{ maxWidth: "280px", marginBottom: "12px" }}>
        <label style={fieldStyle}>
          <span style={labelTextStyle}>student_id</span>
          <input
            type="text"
            value={studentId}
            onChange={(event) => setStudentId(event.target.value)}
            placeholder="e.g. 1001"
            style={inputStyle}
          />
        </label>
      </div>

      <FileUploadArea
        label="Student submission PDF(s)"
        accept="application/pdf,.pdf"
        multiple
        onFilesSelected={setSubmissionFiles}
      />

      <div style={{ marginTop: "12px" }}>
        <button
          type="button"
          onClick={handleUpload}
          disabled={isUploading}
          style={buttonPrimaryStyle}
        >
          {isUploading ? "Uploading..." : "Upload Submission"}
        </button>
      </div>

      {message && (
        <div
          style={{
            ...alertBaseStyle,
            ...(message.type === "success"
              ? {
                  color: "#166534",
                  backgroundColor: "#dcfce7",
                  border: "1px solid #86efac",
                }
              : {
                  color: "#991b1b",
                  backgroundColor: "#fee2e2",
                  border: "1px solid #fca5a5",
                }),
          }}
        >
          {message.text}
        </div>
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

const sectionTitleStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "12px",
  fontSize: "1.2rem",
  color: "#0f172a",
};

const hintStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "10px",
  color: "#475569",
  fontSize: "0.92rem",
  lineHeight: 1.5,
};

const fieldStyle: React.CSSProperties = {
  display: "grid",
  gap: "6px",
};

const labelTextStyle: React.CSSProperties = {
  fontSize: "0.9rem",
  color: "#334155",
};

const inputStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.95rem",
  outline: "none",
};

const buttonPrimaryStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "8px 12px",
  cursor: "pointer",
};

const alertBaseStyle: React.CSSProperties = {
  marginTop: "12px",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.92rem",
};

export default StudentSubmissionPortal;
