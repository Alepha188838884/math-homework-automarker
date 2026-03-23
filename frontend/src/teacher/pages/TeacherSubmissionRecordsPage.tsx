import React from "react";
import GradeResultModal from "../../components/GradeResultModal";
import SubmissionList from "../../components/SubmissionList";
import {
  alertBaseStyle,
  cardStyle,
  messageStyle,
  pageStackStyle,
  sectionTitleStyle,
} from "../styles";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";


function TeacherSubmissionRecordsPage() {
  const {
    modalResult,
    isModalOpen,
    gradingIds,
    viewingIds,
    submissions,
    actionMessage,
    gradeSubmissionById,
    viewSubmissionResult,
    closeResultModal,
  } = useTeacherWorkspace();

  return (
    <div style={pageStackStyle}>
      <section style={cardStyle}>
        <h2 style={sectionTitleStyle}>提交记录</h2>
        <SubmissionList
          submissions={submissions}
          gradingIds={gradingIds}
          viewingIds={viewingIds}
          onGrade={gradeSubmissionById}
          onViewResult={viewSubmissionResult}
        />
        {actionMessage && (
          <div style={{ ...alertBaseStyle, ...messageStyle(actionMessage.type) }}>
            {actionMessage.text}
          </div>
        )}
      </section>

      <GradeResultModal isOpen={isModalOpen} result={modalResult} onClose={closeResultModal} />
    </div>
  );
}

export default TeacherSubmissionRecordsPage;
