from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    courses: Mapped[list[Course]] = relationship("Course", back_populates="teacher")
    assignments: Mapped[list[Assignment]] = relationship("Assignment", back_populates="teacher")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    join_token: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    teacher: Mapped[Teacher] = relationship("Teacher", back_populates="courses")
    students: Mapped[list[Student]] = relationship("Student", back_populates="course")
    assignments: Mapped[list[Assignment]] = relationship("Assignment", back_populates="course")


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    course: Mapped[Course] = relationship("Course", back_populates="students")
    submissions: Mapped[list[Submission]] = relationship("Submission", back_populates="student")


class Assignment(Base):
    __tablename__ = "assignments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), nullable=False, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    max_score: Mapped[float] = mapped_column(Float, default=100.0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)

    teacher: Mapped[Teacher] = relationship("Teacher", back_populates="assignments")
    course: Mapped[Course] = relationship("Course", back_populates="assignments")
    answer_file: Mapped[AnswerFile | None] = relationship(
        "AnswerFile",
        back_populates="assignment",
        uselist=False,
    )
    submissions: Mapped[list[Submission]] = relationship("Submission", back_populates="assignment")


class AnswerFile(Base):
    __tablename__ = "answer_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("assignments.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    qwen_file_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    assignment: Mapped[Assignment] = relationship("Assignment", back_populates="answer_file")


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("assignments.id"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    qwen_file_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    assignment: Mapped[Assignment] = relationship("Assignment", back_populates="submissions")
    student: Mapped[Student] = relationship("Student", back_populates="submissions")
    grade_result: Mapped[GradeResult | None] = relationship(
        "GradeResult",
        back_populates="submission",
        uselist=False,
    )


class GradeResult(Base):
    __tablename__ = "grade_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    submission_id: Mapped[int] = mapped_column(
        ForeignKey("submissions.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, default="qwen3.5-plus")
    raw_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, nullable=False)
    max_total_score: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    submission: Mapped[Submission] = relationship("Submission", back_populates="grade_result")
    questions: Mapped[list[GradeQuestion]] = relationship(
        "GradeQuestion",
        back_populates="grade_result",
        order_by="GradeQuestion.question_number",
    )


class GradeQuestion(Base):
    __tablename__ = "grade_questions"
    __table_args__ = (
        UniqueConstraint("grade_result_id", "question_number", name="uq_grade_question_per_result"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    grade_result_id: Mapped[int] = mapped_column(
        ForeignKey("grade_results.id"),
        nullable=False,
        index=True,
    )
    question_number: Mapped[int] = mapped_column(Integer, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    max_score: Mapped[float] = mapped_column(Float, nullable=False)
    comment: Mapped[str | None] = mapped_column(String(2000), nullable=True)

    grade_result: Mapped[GradeResult] = relationship("GradeResult", back_populates="questions")
