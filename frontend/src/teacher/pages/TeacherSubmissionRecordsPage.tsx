import React from "react";
import GradeResultModal from "../../components/GradeResultModal";
import SubmissionList from "../../components/SubmissionList";
import { useTeacherWorkspace } from "../TeacherWorkspaceContext";

function TeacherSubmissionRecordsPage() {
  const {
    modalResult, isModalOpen, gradingIds, viewingIds, submissions,
    actionMessage, submissionDataError,
    gradeSubmissionById, viewSubmissionResult, closeResultModal,
  } = useTeacherWorkspace();

  return (
    <div className="page-stack">
      <section className="card">
        <h2 className="section-title">提交记录</h2>
        {submissionDataError && <div className="alert alert-error" style={{ marginBottom: "14px" }}>{submissionDataError}</div>}
        <SubmissionList submissions={submissions} gradingIds={gradingIds} viewingIds={viewingIds} onGrade={gradeSubmissionById} onViewResult={viewSubmissionResult} />
        {actionMessage && <div className={`alert alert-${actionMessage.type}`} style={{ marginTop: "14px" }}>{actionMessage.text}</div>}
      </section>
      <GradeResultModal isOpen={isModalOpen} result={modalResult} onClose={closeResultModal} />
    </div>
  );
}

export default TeacherSubmissionRecordsPage;
