import React, { useEffect, useState } from "react";
import { createCourse, generateCourseJoinLink, type Course } from "../../api";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { getErrorMessage, type StatusMessage } from "../../utils";

function courseLabel(course: Course): string {
  return course.description ? `${course.name} - ${course.description}` : course.name;
}

function TeacherCoursesPage() {
  const {
    backendBaseUrl, applyBackendBaseUrl, courses, selectedCourseId,
    isLoadingCourses, coursesError, setSelectedCourseId, loadCourses,
    deleteCourseById, actionMessage,
  } = useTeacherWorkspace();

  const [baseUrlInput, setBaseUrlInput] = useState(backendBaseUrl);
  const [baseUrlMessage, setBaseUrlMessage] = useState<StatusMessage | null>(null);
  const [courseMessage, setCourseMessage] = useState<StatusMessage | null>(null);
  const [joinLinkMessage, setJoinLinkMessage] = useState<StatusMessage | null>(null);
  const [newCourseName, setNewCourseName] = useState("");
  const [newCourseDescription, setNewCourseDescription] = useState("");
  const [latestJoinUrl, setLatestJoinUrl] = useState("");
  const [isCreatingCourse, setIsCreatingCourse] = useState(false);
  const [isGeneratingJoinLink, setIsGeneratingJoinLink] = useState(false);

  useEffect(() => { setBaseUrlInput(backendBaseUrl); }, [backendBaseUrl]);
  useEffect(() => { setLatestJoinUrl(""); setJoinLinkMessage(null); }, [selectedCourseId]);

  const handleApplyBaseUrl = async () => {
    setBaseUrlMessage(null);
    try {
      await applyBackendBaseUrl(baseUrlInput);
      setBaseUrlMessage({ type: "success", text: `后端地址已更新为 ${baseUrlInput.trim()}` });
    } catch (error) { setBaseUrlMessage({ type: "error", text: getErrorMessage(error) }); }
  };

  const handleCreateCourse = async (event: React.FormEvent) => {
    event.preventDefault();
    setCourseMessage(null);
    try {
      setIsCreatingCourse(true);
      const course = await createCourse(newCourseName.trim(), newCourseDescription.trim() || undefined);
      await loadCourses();
      setSelectedCourseId(course.id);
      setNewCourseName(""); setNewCourseDescription("");
      setCourseMessage({ type: "success", text: "班级创建成功。" });
    } catch (error) { setCourseMessage({ type: "error", text: getErrorMessage(error) }); }
    finally { setIsCreatingCourse(false); }
  };

  const handleGenerateJoinLink = async () => {
    setJoinLinkMessage(null);
    if (selectedCourseId === null) { setJoinLinkMessage({ type: "error", text: "请先选择班级。" }); return; }
    try {
      setIsGeneratingJoinLink(true);
      const response = await generateCourseJoinLink(selectedCourseId);
      setLatestJoinUrl(response.join_url);
      setJoinLinkMessage({ type: "success", text: "加入链接已生成，旧链接已失效。" });
    } catch (error) { setJoinLinkMessage({ type: "error", text: getErrorMessage(error) }); }
    finally { setIsGeneratingJoinLink(false); }
  };

  const handleDeleteCourse = (courseId: number) => {
    if (window.confirm("删除课程将同时删除其学生、作业与全部提交，且不可恢复。确定删除？")) {
      void deleteCourseById(courseId);
    }
  };

  const handleCopyJoinLink = async () => {
    if (!latestJoinUrl) { setJoinLinkMessage({ type: "error", text: "请先生成加入链接。" }); return; }
    try {
      await navigator.clipboard.writeText(latestJoinUrl);
      setJoinLinkMessage({ type: "success", text: "链接已复制到剪贴板。" });
    } catch { setJoinLinkMessage({ type: "error", text: "复制失败，请手动复制链接。" }); }
  };

  return (
    <div className="page-stack">
      {import.meta.env.DEV && (
        <section className="card">
          <h2 className="section-title">班级管理</h2>
          <div className="grid">
            <label className="form-group" style={{ gridColumn: "1 / span 2" }}>
              <span className="form-label">后端地址（仅开发环境显示）</span>
              <input type="text" value={baseUrlInput} onChange={(e) => setBaseUrlInput(e.target.value)} placeholder="http://localhost:8000" className="form-input" />
            </label>
            <div style={{ display: "flex", alignItems: "flex-end" }}>
              <button type="button" onClick={handleApplyBaseUrl} className="btn btn-secondary">应用</button>
            </div>
          </div>
          {baseUrlMessage && <div className={`alert alert-${baseUrlMessage.type}`} style={{ marginTop: "12px" }}>{baseUrlMessage.text}</div>}
        </section>
      )}

      <section className="card">
        <div className="header-row">
          <h2 className="section-title">已有班级与创建班级</h2>
          <button type="button" className="btn btn-secondary" disabled={isLoadingCourses} onClick={() => void loadCourses()}>
            {isLoadingCourses ? "加载中..." : "刷新班级"}
          </button>
        </div>
        <div className="split-grid">
          <div>
            <h3 className="sub-title">已有班级</h3>
            {courses.length === 0 ? (
              <div className="empty-state">暂无班级</div>
            ) : (
              <div style={{ display: "grid", gap: "8px" }}>
                {courses.map((c) => (
                  <div key={c.id} style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <button type="button" onClick={() => setSelectedCourseId(c.id)} className={`selection-btn${selectedCourseId === c.id ? " active" : ""}`} style={{ flex: 1, minWidth: 0 }}>
                      <strong>#{c.id}</strong> {courseLabel(c)}
                    </button>
                    <button type="button" className="btn btn-danger" onClick={() => handleDeleteCourse(c.id)}>删除</button>
                  </div>
                ))}
              </div>
            )}
            {coursesError && <div className="alert alert-error" style={{ marginTop: "12px" }}>{coursesError}</div>}
            {actionMessage && <div className={`alert alert-${actionMessage.type}`} style={{ marginTop: "12px" }}>{actionMessage.text}</div>}
          </div>
          <div>
            <h3 className="sub-title">创建班级</h3>
            <form onSubmit={handleCreateCourse} className="form-stack">
              <label className="form-group">
                <span className="form-label">班级名称</span>
                <input className="form-input" value={newCourseName} onChange={(e) => setNewCourseName(e.target.value)} required />
              </label>
              <label className="form-group">
                <span className="form-label">描述（可选）</span>
                <input className="form-input" value={newCourseDescription} onChange={(e) => setNewCourseDescription(e.target.value)} />
              </label>
              <button type="submit" className="btn btn-primary" disabled={isCreatingCourse}>
                {isCreatingCourse ? "创建中..." : "创建班级"}
              </button>
            </form>
          </div>
        </div>
        {courseMessage && <div className={`alert alert-${courseMessage.type}`} style={{ marginTop: "12px" }}>{courseMessage.text}</div>}
      </section>

      <section className="card">
        <h2 className="section-title">学生加入链接</h2>
        <div className="inline-info">
          <div style={{ marginBottom: "10px", fontWeight: 600 }}>当前班级学生加入入口</div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
            <button type="button" className="btn btn-secondary" onClick={handleGenerateJoinLink} disabled={selectedCourseId === null || isGeneratingJoinLink}>
              {isGeneratingJoinLink ? "生成中..." : "生成加入链接"}
            </button>
            <input className="form-input" style={{ minWidth: 0, flex: 1 }} value={latestJoinUrl} placeholder="生成后会显示可分享给学生的链接" readOnly />
            <button type="button" className="btn btn-secondary" onClick={() => void handleCopyJoinLink()} disabled={!latestJoinUrl}>复制</button>
          </div>
          <div style={{ marginTop: "8px", color: "var(--text-secondary)", fontSize: "0.84rem" }}>重新生成会立即覆盖旧链接，旧链接将失效。</div>
        </div>
        {joinLinkMessage && <div className={`alert alert-${joinLinkMessage.type}`} style={{ marginTop: "12px" }}>{joinLinkMessage.text}</div>}
      </section>
    </div>
  );
}

export default TeacherCoursesPage;
