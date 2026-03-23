import React from "react";
import {
  alertBaseStyle,
  cardStyle,
  emptyBoxStyle,
  inlineInfoStyle,
  messageStyle,
  pageStackStyle,
  sectionTitleStyle,
  tableStyle,
  tdStyle,
  thStyle,
} from "../styles";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";


function TeacherSubmissionStatusPage() {
  const {
    selectedAssignmentId,
    studentsStatus,
    actionMessage,
    submissionDataError,
    isLoadingSubmissionData,
  } = useTeacherWorkspace();

  return (
    <div style={pageStackStyle}>
      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>学生提交状态</h2>
        {selectedAssignmentId === null ? (
          <div style={emptyBoxStyle}>请选择作业后查看状态。</div>
        ) : isLoadingSubmissionData ? (
          <div style={emptyBoxStyle}>加载中...</div>
        ) : studentsStatus.length === 0 ? (
          <div style={emptyBoxStyle}>当前班级暂无学生或暂无状态数据。</div>
        ) : (
          <>
            <div style={inlineInfoStyle}>当前作业提交状态会每 10 秒自动刷新。</div>
            <table style={tableStyle}>
              <thead>
                <tr>
                  <th style={thStyle}>Student Name</th>
                  <th style={thStyle}>Email</th>
                  <th style={thStyle}>Has Submitted</th>
                  <th style={thStyle}>Submission Status</th>
                  <th style={thStyle}>Score</th>
                </tr>
              </thead>
              <tbody>
                {studentsStatus.map((item) => (
                  <tr key={item.student_id}>
                    <td style={tdStyle}>{item.student_name}</td>
                    <td style={tdStyle}>{item.student_email}</td>
                    <td style={tdStyle}>{item.has_submitted ? "Yes" : "No"}</td>
                    <td style={tdStyle}>{item.submission_status ?? "-"}</td>
                    <td style={tdStyle}>
                      {item.submission_status === "needs_manual_review" &&
                      item.total_score !== null &&
                      item.max_total_score !== null
                        ? `自动评分小计 ${item.total_score} / ${item.max_total_score}`
                        : item.total_score !== null && item.max_total_score !== null
                          ? `${item.total_score} / ${item.max_total_score}`
                          : "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        {actionMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(actionMessage.type) }}>
            {actionMessage.text}
          </div>
        )}
        {submissionDataError && (
          <div style={{ ...alertBaseStyle, ...messageStyle("error") }}>{submissionDataError}</div>
        )}
      </section>
    </div>
  );
}

export default TeacherSubmissionStatusPage;
