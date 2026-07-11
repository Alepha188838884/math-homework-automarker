import React, { useRef, useState } from "react";

export interface FileUploadAreaProps {
  accept: string;
  multiple?: boolean;
  onFilesSelected: (files: File[]) => void;
  label: string;
}

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
    if (files.length === 0) return;
    setFiles(files);
  };

  const clearSelection = () => {
    setSelectedFiles([]);
    onFilesSelected([]);
    if (inputRef.current) inputRef.current.value = "";
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
        className={`dropzone${isDragOver ? " drag-active" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragOver(true); }}
        onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragOver(false); }}
        onDrop={handleDrop}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
      >
        <div className="dropzone-label">{label}</div>
        <div className="dropzone-hint">拖拽文件到此处，或点击选择文件</div>
        <div className="dropzone-accept">
          支持格式：
          {accept
            .split(",")
            .map((part) => part.trim())
            .filter((part) => part.startsWith("."))
            .join("、") || accept}
        </div>
      </div>

      {selectedFiles.length > 0 && (
        <div className="file-list">
          <div className="file-list-title">已选择文件</div>
          <ul style={{ margin: 0, paddingLeft: "20px", color: "var(--text)" }}>
            {selectedFiles.map((file) => (
              <li key={`${file.name}-${file.lastModified}`}>{file.name}</li>
            ))}
          </ul>
          <button
            type="button"
            onClick={clearSelection}
            className="btn btn-secondary"
            style={{ marginTop: "10px" }}
          >
            清除
          </button>
        </div>
      )}
    </div>
  );
}

export default FileUploadArea;
