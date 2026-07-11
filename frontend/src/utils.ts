import type { GradeAllFailure } from "./api";


export type MessageType = "success" | "error" | "info";

export interface StatusMessage {
  type: MessageType;
  text: string;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误";
}

export function isDocxFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".docx");
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
}

export function isPdfFile(file: File): boolean {
  return file.name.toLowerCase().endsWith(".pdf");
}

export const statusLabels: Record<string, string> = {
  uploaded: "已上传",
  grading: "批改中",
  graded: "已批改",
  needs_manual_review: "待人工复核",
  failed_grading: "批改失败",
  failed_upload: "上传失败",
};

export function statusLabel(status: string): string {
  return Object.prototype.hasOwnProperty.call(statusLabels, status) ? statusLabels[status] : status;
}

export function getFailureReason(failure: GradeAllFailure): string {
  return failure.reason ?? failure.detail ?? "未知错误";
}
