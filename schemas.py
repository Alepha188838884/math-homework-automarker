from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TeacherPublic(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class StudentPublic(BaseModel):
    id: int
    name: str
    email: str
    course_id: int

    model_config = ConfigDict(from_attributes=True)


class TeacherLoginRequest(BaseModel):
    email: str
    password: str


class StudentLoginRequest(BaseModel):
    email: str
    password: str


class TeacherEntryRequest(BaseModel):
    name: str | None = None
    email: str
    password: str


class StudentEntryRequest(BaseModel):
    name: str | None = None
    email: str
    password: str
    assignment_id: int | None = None


class BootstrapTeacherRequest(BaseModel):
    name: str
    email: str
    password: str


class TeacherLoginResponse(Token):
    teacher: TeacherPublic


class StudentLoginResponse(Token):
    student: StudentPublic


class CourseCreate(BaseModel):
    name: str
    description: str | None = None


class CourseOut(BaseModel):
    id: int
    teacher_id: int
    name: str
    description: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CourseJoinInfo(BaseModel):
    course_id: int
    course_name: str
    teacher_name: str | None = None


class JoinLinkResponse(BaseModel):
    course_id: int
    join_token: str
    join_url: str


class StudentCreate(BaseModel):
    name: str
    email: str
    password: str


class StudentJoinRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class StudentJoinResponse(BaseModel):
    student_id: int
    course_id: int
    email: EmailStr
    access_token: str | None = None
    token_type: str | None = None


class AssignmentCreate(BaseModel):
    title: str
    description: str | None = None
    due_date: datetime | None = None
    max_score: float | None = None


class AnswerFileResponse(BaseModel):
    id: int
    assignment_id: int
    original_filename: str
    file_path: str
    qwen_file_id: str
    uploaded_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionResponse(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    original_filename: str
    file_path: str
    qwen_file_id: str | None
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    graded_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class AssignmentOut(BaseModel):
    id: int
    teacher_id: int
    course_id: int
    title: str
    description: str | None = None
    due_date: datetime | None = None
    max_score: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubmissionOut(BaseModel):
    id: int
    assignment_id: int
    student_id: int
    original_filename: str
    status: str
    created_at: datetime
    graded_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class StudentAssignmentStatus(BaseModel):
    student_id: int
    student_name: str
    student_email: str
    has_submitted: bool
    submission_id: int | None
    submission_status: str | None
    total_score: float | None
    max_total_score: float | None


class StudentAssignmentOverview(BaseModel):
    assignment_id: int
    title: str
    description: str | None
    created_at: datetime
    due_date: datetime | None
    max_score: float | None
    has_submitted: bool
    submission_id: int | None
    submission_status: str | None
    total_score: float | None
    max_total_score: float | None


class GradeQuestionItem(BaseModel):
    number: int = Field(ge=1)
    is_correct: bool | None
    score: float | None
    max_score: float
    comment: str | None = None


class GradeSubmissionResponse(BaseModel):
    submission_id: int
    status: str
    questions: list[GradeQuestionItem]
    total_score: float
    max_total_score: float


class SubmissionResultResponse(BaseModel):
    submission_id: int
    status: str
    model_name: str
    graded_at: datetime | None
    questions: list[GradeQuestionItem]
    total_score: float
    max_total_score: float


class GradeAllFailure(BaseModel):
    submission_id: int
    detail: str


class GradeAllSummary(BaseModel):
    assignment_id: int
    total: int
    graded: int
    failed: int
    skipped: int
    failures: list[GradeAllFailure]
