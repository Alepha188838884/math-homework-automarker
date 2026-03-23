import type { GradeAllFailure } from "../api";


export type MessageType = "success" | "error" | "info";

export interface StatusMessage {
  type: MessageType;
  text: string;
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
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
  return date.toLocaleString();
}

export function getFailureReason(failure: GradeAllFailure): string {
  return failure.reason ?? failure.detail ?? "Unknown error";
}
