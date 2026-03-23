import type { CSSProperties } from "react";
import type { MessageType } from "./utils";


export const pageStackStyle: CSSProperties = {
  display: "grid",
  gap: "16px",
};

export const layoutShellStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "240px minmax(0, 1fr)",
  gap: "16px",
  alignItems: "start",
};

export const sidebarStyle: CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "18px 14px",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
  position: "sticky",
  top: "12px",
};

export const sidebarTitleStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.05rem",
  color: "#0f172a",
};

export const sidebarHintStyle: CSSProperties = {
  margin: "6px 0 0",
  color: "#64748b",
  fontSize: "0.88rem",
  lineHeight: 1.5,
};

export const navListStyle: CSSProperties = {
  display: "grid",
  gap: "8px",
  marginTop: "18px",
};

export function navLinkStyle(isActive: boolean): CSSProperties {
  return {
    display: "block",
    textDecoration: "none",
    borderRadius: "10px",
    padding: "10px 12px",
    border: isActive ? "1px solid #60a5fa" : "1px solid #e2e8f0",
    backgroundColor: isActive ? "#eff6ff" : "#ffffff",
    color: isActive ? "#1d4ed8" : "#0f172a",
    fontWeight: isActive ? 700 : 500,
  };
}

export const contentShellStyle: CSSProperties = {
  display: "grid",
  gap: "16px",
  minWidth: 0,
};

export const layoutTopCardStyle: CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "16px",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
};

export const layoutTopBarStyle: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  gap: "16px",
  flexWrap: "wrap",
};

export const layoutHeadingStyle: CSSProperties = {
  margin: 0,
  fontSize: "1.2rem",
  color: "#0f172a",
};

export const layoutSubHeadingStyle: CSSProperties = {
  margin: "6px 0 0",
  color: "#475569",
  fontSize: "0.92rem",
};

export const topActionsStyle: CSSProperties = {
  display: "flex",
  gap: "10px",
  flexWrap: "wrap",
  alignItems: "center",
};

export const selectorsGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
  gap: "12px",
  marginTop: "14px",
};

export const cardStyle: CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "16px",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
};

export const sectionTitleStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: "12px",
  fontSize: "1.2rem",
  color: "#0f172a",
};

export const subTitleStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: "10px",
  fontSize: "1rem",
  color: "#1e293b",
};

export const contextHintStyle: CSSProperties = {
  marginTop: 0,
  marginBottom: 0,
  color: "#475569",
  fontSize: "0.92rem",
  lineHeight: 1.5,
};

export const headerRowStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: "12px",
  flexWrap: "wrap",
};

export const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
  gap: "12px",
};

export const splitGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
  gap: "14px",
};

export const formStyle: CSSProperties = {
  display: "grid",
  gap: "10px",
};

export const fieldStyle: CSSProperties = {
  display: "grid",
  gap: "6px",
};

export const labelTextStyle: CSSProperties = {
  fontSize: "0.9rem",
  color: "#334155",
};

export const inputStyle: CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.95rem",
  outline: "none",
  backgroundColor: "#ffffff",
  color: "#0f172a",
};

export const buttonPrimaryStyle: CSSProperties = {
  border: "none",
  borderRadius: "8px",
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "8px 12px",
  cursor: "pointer",
};

export const buttonSecondaryStyle: CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  backgroundColor: "#ffffff",
  color: "#0f172a",
  padding: "8px 12px",
  cursor: "pointer",
};

export const alertBaseStyle: CSSProperties = {
  marginTop: "12px",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.92rem",
};

export function messageStyle(type: MessageType): CSSProperties {
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

export const debugInfoStyle: CSSProperties = {
  marginTop: "10px",
  fontSize: "0.9rem",
  color: "#334155",
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "8px",
  padding: "10px",
  display: "grid",
  gap: "4px",
};

export const summaryPanelStyle: CSSProperties = {
  marginTop: "12px",
  backgroundColor: "#f8fafc",
  border: "1px solid #e2e8f0",
  borderRadius: "10px",
  padding: "10px 12px",
  color: "#0f172a",
};

export const summaryGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
  gap: "8px",
};

export const emptyBoxStyle: CSSProperties = {
  border: "1px dashed #cbd5e1",
  borderRadius: "8px",
  padding: "12px",
  color: "#64748b",
  backgroundColor: "#f8fafc",
};

export const inlineInfoStyle: CSSProperties = {
  color: "#1e3a8a",
  backgroundColor: "#dbeafe",
  border: "1px solid #93c5fd",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.9rem",
};

export const selectionButtonStyle: CSSProperties = {
  textAlign: "left",
  border: "1px solid #cbd5e1",
  backgroundColor: "#ffffff",
  color: "#0f172a",
  borderRadius: "8px",
  padding: "8px 10px",
  cursor: "pointer",
};

export const selectionButtonActiveStyle: CSSProperties = {
  borderColor: "#60a5fa",
  backgroundColor: "#eff6ff",
};

export const tableStyle: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  border: "1px solid #e2e8f0",
  backgroundColor: "#ffffff",
};

export const thStyle: CSSProperties = {
  textAlign: "left",
  padding: "10px",
  backgroundColor: "#f8fafc",
  borderBottom: "1px solid #e2e8f0",
  color: "#334155",
  fontSize: "0.9rem",
};

export const tdStyle: CSSProperties = {
  padding: "10px",
  borderBottom: "1px solid #e2e8f0",
  color: "#0f172a",
  fontSize: "0.92rem",
  verticalAlign: "top",
};
