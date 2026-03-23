import React, { useState } from "react";
import { createAssignment } from "../../api";
import {
  alertBaseStyle,
  buttonPrimaryStyle,
  buttonSecondaryStyle,
  cardStyle,
  emptyBoxStyle,
  fieldStyle,
  formStyle,
  headerRowStyle,
  inlineInfoStyle,
  inputStyle,
  labelTextStyle,
  messageStyle,
  pageStackStyle,
  sectionTitleStyle,
  splitGridStyle,
  subTitleStyle,
  tableStyle,
  tdStyle,
  thStyle,
} from "../styles";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";
import { formatDateTime, getErrorMessage, type StatusMessage } from "../utils";


function TeacherAssignmentsPage() {
  const {
    selectedCourseId,
    selectedAssignmentId,
    setSelectedAssignmentId,
    courseAssignments,
    assignmentsError,
    isLoadingAssignments,
    loadAssignmentsForCourse,
  } = useTeacherWorkspace();

  const [newAssignmentTitle, setNewAssignmentTitle] = useState<string>("");
  const [newAssignmentDescription, setNewAssignmentDescription] = useState<string>("");
  const [newAssignmentDueDate, setNewAssignmentDueDate] = useState<string>("");
  const [newAssignmentMaxScore, setNewAssignmentMaxScore] = useState<string>("");
  const [isCreatingAssignment, setIsCreatingAssignment] = useState<boolean>(false);
  const [assignmentMessage, setAssignmentMessage] = useState<StatusMessage | null>(null);

  const handleCreateAssignment = async (event: React.FormEvent) => {
    event.preventDefault();
    setAssignmentMessage(null);
    if (selectedCourseId === null) {
      setAssignmentMessage({ type: "error", text: "请先选择班级。" });
      return;
    }

    try {
      setIsCreatingAssignment(true);
      const title = newAssignmentTitle.trim();
      const description = newAssignmentDescription.trim() || undefined;
      const dueDate = newAssignmentDueDate.trim()
        ? new Date(newAssignmentDueDate).toISOString()
        : undefined;

      let maxScore: number | undefined;
      if (newAssignmentMaxScore.trim()) {
        const parsed = Number(newAssignmentMaxScore);
        if (!Number.isFinite(parsed) || parsed <= 0) {
          setAssignmentMessage({ type: "error", text: "max_score 必须是正数。" });
          return;
        }
        maxScore = parsed;
      }

      const assignment = await createAssignment(selectedCourseId, {
        title,
        description,
        due_date: dueDate,
        max_score: maxScore,
      });

      await loadAssignmentsForCourse(selectedCourseId);
      setSelectedAssignmentId(assignment.id);
      setNewAssignmentTitle("");
      setNewAssignmentDescription("");
      setNewAssignmentDueDate("");
      setNewAssignmentMaxScore("");
      setAssignmentMessage({ type: "success", text: "作业创建成功。" });
    } catch (error) {
      setAssignmentMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsCreatingAssignment(false);
    }
  };

  return (
    <div style={pageStackStyle}>
      <section style={cardStyle}>
        <div style={headerRowStyle}>
          <h2 style={sectionTitleStyle}>作业管理</h2>
          <button
            type="button"
            style={buttonSecondaryStyle}
            disabled={isLoadingAssignments || selectedCourseId === null}
            onClick={() => {
              if (selectedCourseId !== null) {
                void loadAssignmentsForCourse(selectedCourseId);
              }
            }}
          >
            {isLoadingAssignments ? "Loading..." : "Refresh assignments"}
          </button>
        </div>

        <div style={splitGridStyle}>
          <div>
            <h3 style={subTitleStyle}>当前班级作业</h3>
            {selectedCourseId === null ? (
              <div style={emptyBoxStyle}>请先在顶部选择班级</div>
            ) : (
              <>
                <div style={{ display: "flex", gap: "10px", flexWrap: "wrap", marginBottom: "10px" }}>
                  <select
                    style={{ ...inputStyle, minWidth: "280px" }}
                    value={selectedAssignmentId ?? ""}
                    onChange={(event) => {
                      const value = Number(event.target.value);
                      setSelectedAssignmentId(Number.isFinite(value) && value > 0 ? value : null);
                    }}
                    disabled={isLoadingAssignments || courseAssignments.length === 0}
                  >
                    {courseAssignments.length === 0 ? (
                      <option value="">No assignments</option>
                    ) : (
                      courseAssignments.map((assignment) => (
                        <option key={assignment.id} value={assignment.id}>
                          #{assignment.id} - {assignment.title}
                        </option>
                      ))
                    )}
                  </select>
                </div>

                {courseAssignments.length === 0 ? (
                  <div style={emptyBoxStyle}>当前班级暂无作业。</div>
                ) : (
                  <div style={{ overflowX: "auto" }}>
                    <table style={tableStyle}>
                      <thead>
                        <tr>
                          <th style={thStyle}>ID</th>
                          <th style={thStyle}>Title</th>
                          <th style={thStyle}>Due Date</th>
                          <th style={thStyle}>Max Score</th>
                          <th style={thStyle}>Created At</th>
                        </tr>
                      </thead>
                      <tbody>
                        {courseAssignments.map((assignment) => (
                          <tr key={`assignment-row-${assignment.id}`}>
                            <td style={tdStyle}>{assignment.id}</td>
                            <td style={tdStyle}>{assignment.title}</td>
                            <td style={tdStyle}>{formatDateTime(assignment.due_date)}</td>
                            <td style={tdStyle}>{assignment.max_score ?? "-"}</td>
                            <td style={tdStyle}>{formatDateTime(assignment.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {selectedAssignmentId && (
                  <div style={inlineInfoStyle}>当前作业提交状态会每 10 秒自动刷新。</div>
                )}
              </>
            )}
            {assignmentsError && (
              <div style={{ ...alertBaseStyle, ...messageStyle("error") }}>{assignmentsError}</div>
            )}
          </div>

          <div>
            <h3 style={subTitleStyle}>创建作业</h3>
            <form onSubmit={handleCreateAssignment} style={formStyle}>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Title</span>
                <input
                  style={inputStyle}
                  value={newAssignmentTitle}
                  onChange={(event) => setNewAssignmentTitle(event.target.value)}
                  required
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Description (optional)</span>
                <input
                  style={inputStyle}
                  value={newAssignmentDescription}
                  onChange={(event) => setNewAssignmentDescription(event.target.value)}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Due Date (optional)</span>
                <input
                  style={inputStyle}
                  type="datetime-local"
                  value={newAssignmentDueDate}
                  onChange={(event) => setNewAssignmentDueDate(event.target.value)}
                />
              </label>
              <label style={fieldStyle}>
                <span style={labelTextStyle}>Max Score (optional)</span>
                <input
                  style={inputStyle}
                  type="number"
                  min="0"
                  step="0.5"
                  placeholder="默认 100"
                  value={newAssignmentMaxScore}
                  onChange={(event) => setNewAssignmentMaxScore(event.target.value)}
                />
              </label>
              <button type="submit" style={buttonPrimaryStyle} disabled={isCreatingAssignment}>
                {isCreatingAssignment ? "Creating..." : "Create Assignment"}
              </button>
            </form>
          </div>
        </div>

        {assignmentMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(assignmentMessage.type) }}>
            {assignmentMessage.text}
          </div>
        )}
      </section>
    </div>
  );
}

export default TeacherAssignmentsPage;
