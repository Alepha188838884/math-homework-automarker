import React, { useEffect, useState } from "react";
import {
  createCourse,
  generateCourseJoinLink,
  type Course,
} from "../../api";
import {
  alertBaseStyle,
  buttonPrimaryStyle,
  buttonSecondaryStyle,
  cardStyle,
  emptyBoxStyle,
  fieldStyle,
  formStyle,
  gridStyle,
  headerRowStyle,
  inlineInfoStyle,
  inputStyle,
  labelTextStyle,
  messageStyle,
  pageStackStyle,
  sectionTitleStyle,
  selectionButtonActiveStyle,
  selectionButtonStyle,
  splitGridStyle,
  subTitleStyle,
} from "../styles";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { getErrorMessage, type StatusMessage } from "../utils";


function courseLabel(course: Course): string {
  return course.description ? `${course.name} - ${course.description}` : course.name;
}

function TeacherCoursesPage() {
  const {
    backendBaseUrl,
    applyBackendBaseUrl,
    courses,
    selectedCourseId,
    isLoadingCourses,
    coursesError,
    setSelectedCourseId,
    loadCourses,
  } = useTeacherWorkspace();

  const [baseUrlInput, setBaseUrlInput] = useState<string>(backendBaseUrl);
  const [baseUrlMessage, setBaseUrlMessage] = useState<StatusMessage | null>(null);
  const [courseMessage, setCourseMessage] = useState<StatusMessage | null>(null);
  const [joinLinkMessage, setJoinLinkMessage] = useState<StatusMessage | null>(null);
  const [newCourseName, setNewCourseName] = useState<string>("");
  const [newCourseDescription, setNewCourseDescription] = useState<string>("");
  const [latestJoinUrl, setLatestJoinUrl] = useState<string>("");
  const [isCreatingCourse, setIsCreatingCourse] = useState<boolean>(false);
  const [isGeneratingJoinLink, setIsGeneratingJoinLink] = useState<boolean>(false);

  useEffect(() => {
    setBaseUrlInput(backendBaseUrl);
  }, [backendBaseUrl]);

  useEffect(() => {
    setLatestJoinUrl("");
    setJoinLinkMessage(null);
  }, [selectedCourseId]);

  const handleApplyBaseUrl = async () => {
    setBaseUrlMessage(null);
    try {
      await applyBackendBaseUrl(baseUrlInput);
      setBaseUrlMessage({
        type: "success",
        text: `Backend URL updated to ${baseUrlInput.trim()}`,
      });
    } catch (error) {
      setBaseUrlMessage({ type: "error", text: getErrorMessage(error) });
    }
  };

  const handleCreateCourse = async (event: React.FormEvent) => {
    event.preventDefault();
    setCourseMessage(null);
    try {
      setIsCreatingCourse(true);
      const course = await createCourse(
        newCourseName.trim(),
        newCourseDescription.trim() || undefined,
      );
      await loadCourses();
      setSelectedCourseId(course.id);
      setNewCourseName("");
      setNewCourseDescription("");
      setCourseMessage({ type: "success", text: "班级创建成功。" });
    } catch (error) {
      setCourseMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsCreatingCourse(false);
    }
  };

  const handleGenerateJoinLink = async () => {
    setJoinLinkMessage(null);
    if (selectedCourseId === null) {
      setJoinLinkMessage({ type: "error", text: "请先选择班级。" });
      return;
    }
    try {
      setIsGeneratingJoinLink(true);
      const response = await generateCourseJoinLink(selectedCourseId);
      setLatestJoinUrl(response.join_url);
      setJoinLinkMessage({ type: "success", text: "加入链接已生成，旧链接已失效。" });
    } catch (error) {
      setJoinLinkMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsGeneratingJoinLink(false);
    }
  };

  const handleCopyJoinLink = async () => {
    if (!latestJoinUrl) {
      setJoinLinkMessage({ type: "error", text: "请先生成加入链接。" });
      return;
    }
    try {
      await navigator.clipboard.writeText(latestJoinUrl);
      setJoinLinkMessage({ type: "success", text: "链接已复制到剪贴板。" });
    } catch {
      setJoinLinkMessage({ type: "error", text: "复制失败，请手动复制链接。" });
    }
  };

  return (
    <div style={pageStackStyle}>
      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>班级管理</h2>
        <div style={gridStyle}>
          <label style={{ ...fieldStyle, gridColumn: "1 / span 2" }}>
            <span style={labelTextStyle}>Backend Base URL</span>
            <input
              type="text"
              value={baseUrlInput}
              onChange={(event) => setBaseUrlInput(event.target.value)}
              placeholder="http://localhost:8000"
              style={inputStyle}
            />
          </label>
          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button type="button" onClick={handleApplyBaseUrl} style={buttonSecondaryStyle}>
              Apply
            </button>
          </div>
        </div>
        {baseUrlMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(baseUrlMessage.type) }}>
            {baseUrlMessage.text}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <div style={headerRowStyle}>
          <h2 style={sectionTitleStyle}>已有班级与创建班级</h2>
          <button
            type="button"
            style={buttonSecondaryStyle}
            disabled={isLoadingCourses}
            onClick={() => void loadCourses()}
          >
            {isLoadingCourses ? "Loading..." : "Refresh courses"}
          </button>
        </div>

        <div style={splitGridStyle}>
          <div>
            <h3 style={subTitleStyle}>已有班级</h3>
            {courses.length === 0 ? (
              <div style={emptyBoxStyle}>暂无班级</div>
            ) : (
              <div style={{ display: "grid", gap: "8px" }}>
                {courses.map((course) => (
                  <button
                    key={course.id}
                    type="button"
                    onClick={() => setSelectedCourseId(course.id)}
                    style={{
                      ...selectionButtonStyle,
                      ...(selectedCourseId === course.id ? selectionButtonActiveStyle : {}),
                    }}
                  >
                    <strong>#{course.id}</strong> {courseLabel(course)}
                  </button>
                ))}
              </div>
            )}
            {coursesError && (
              <div style={{ ...alertBaseStyle, ...messageStyle("error") }}>{coursesError}</div>
            )}
          </div>

          <div>
            <h3 style={subTitleStyle}>创建班级</h3>
            <form onSubmit={handleCreateCourse} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Course Name</span>
                <input
                  style={inputStyle}
                  value={newCourseName}
                  onChange={(event) => setNewCourseName(event.target.value)}
                  required
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Description (optional)</span>
                <input
                  style={inputStyle}
                  value={newCourseDescription}
                  onChange={(event) => setNewCourseDescription(event.target.value)}
                />
              </label>
              <button type="submit" style={buttonPrimaryStyle} disabled={isCreatingCourse}>
                {isCreatingCourse ? "Creating..." : "Create Course"}
              </button>
            </form>
          </div>
        </div>

        {courseMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(courseMessage.type) }}>
            {courseMessage.text}
          </div>
        )}
      </section>

      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>学生加入链接</h2>
        <div style={inlineInfoStyle}>
          <div style={{ marginBottom: "10px", fontWeight: 600 }}>当前班级学生加入入口</div>
          <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center" }}>
            <button
              type="button"
              style={buttonSecondaryStyle}
              onClick={handleGenerateJoinLink}
              disabled={selectedCourseId === null || isGeneratingJoinLink}
            >
              {isGeneratingJoinLink ? "Generating..." : "生成加入链接"}
            </button>
            <input
              style={{ ...inputStyle, minWidth: "360px", flex: 1 }}
              value={latestJoinUrl}
              placeholder="生成后会显示可分享给学生的链接"
              readOnly
            />
            <button
              type="button"
              style={buttonSecondaryStyle}
              onClick={() => void handleCopyJoinLink()}
              disabled={!latestJoinUrl}
            >
              复制
            </button>
          </div>
          <div style={{ marginTop: "8px", color: "#334155", fontSize: "0.88rem" }}>
            重新生成会立即覆盖旧链接，旧链接将失效。
          </div>
        </div>

        {joinLinkMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(joinLinkMessage.type) }}>
            {joinLinkMessage.text}
          </div>
        )}
      </section>
    </div>
  );
}

export default TeacherCoursesPage;
