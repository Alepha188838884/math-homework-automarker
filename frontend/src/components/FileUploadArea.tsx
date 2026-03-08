import React, { useRef, useState } from "react";

export interface FileUploadAreaProps {
  accept: string;
  multiple?: boolean;
  onFilesSelected: (files: File[]) => void;
  label: string;
}

const baseDropzoneStyle: React.CSSProperties = {
  border: "2px dashed #94a3b8",
  borderRadius: "12px",
  padding: "20px",
  backgroundColor: "#f8fafc",
  cursor: "pointer",
  transition: "all 0.2s ease",
};

const activeDropzoneStyle: React.CSSProperties = {
  borderColor: "#2563eb",
  backgroundColor: "#eff6ff",
};

function FileUploadArea({
  accept,
  multiple = false,
  onFilesSelected,
  label,
}: FileUploadAreaProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const setFiles = (files: File[]) => {
    const normalized = multiple ? files : files.slice(0, 1);
    setSelectedFiles(normalized);
    onFilesSelected(normalized);
  };

  const handleInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files ? Array.from(event.target.files) : [];
    setFiles(files);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setIsDragOver(false);

    const files = Array.from(event.dataTransfer.files ?? []);
    if (files.length === 0) {
      return;
    }
    setFiles(files);
  };

  const clearSelection = () => {
    setSelectedFiles([]);
    onFilesSelected([]);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  };

  return (
    <div style={{ display: "grid", gap: "10px" }}>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        style={{ display: "none" }}
        onChange={handleInputChange}
      />

      <div
        style={{
          ...baseDropzoneStyle,
          ...(isDragOver ? activeDropzoneStyle : {}),
        }}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setIsDragOver(true);
        }}
        onDragLeave={(event) => {
          event.preventDefault();
          event.stopPropagation();
          setIsDragOver(false);
        }}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <div style={{ fontWeight: 600, color: "#0f172a" }}>{label}</div>
        <div style={{ color: "#475569", marginTop: "6px" }}>
          Drag & drop files here, or click to browse.
        </div>
        <div style={{ color: "#64748b", fontSize: "0.9rem", marginTop: "4px" }}>
          Accepted: {accept}
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div
          style={{
            border: "1px solid #e2e8f0",
            borderRadius: "10px",
            padding: "10px 12px",
            backgroundColor: "#ffffff",
          }}
        >
          <div style={{ fontWeight: 600, marginBottom: "6px", color: "#0f172a" }}>
            Selected files
          </div>
          <ul style={{ margin: 0, paddingLeft: "20px", color: "#334155" }}>
            {selectedFiles.map((file) => (
              <li key={`${file.name}-${file.lastModified}`}>{file.name}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={clearSelection}
            style={{
              marginTop: "10px",
              border: "1px solid #cbd5e1",
              background: "#fff",
              padding: "6px 10px",
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            Clear
          </button>
        </div>
      )}
    </div>
  );
}

export default FileUploadArea;
