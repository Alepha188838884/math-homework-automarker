from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator


def normalize_due_date_to_utc_naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def serialize_due_date_as_utc_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        utc_value = value.replace(tzinfo=timezone.utc)
    else:
        utc_value = value.astimezone(timezone.utc)
    return utc_value.isoformat().replace("+00:00", "Z")


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
    signup_code: str | None = None


class StudentEntryRequest(BaseModel):
    name: str | None = None
    email: str
    password: str
    assignment_id: int | None = None


class BootstrapTeacherRequest(BaseModel):
    name: str
    email: str
    password: str
    signup_code: str | None = None


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
    password: str = Field(min_length=8)


class StudentJoinRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)


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

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, value: datetime | None) -> datetime | None:
        return normalize_due_date_to_utc_naive(value)


class AnswerFileResponse(BaseModel):
    id: int
    assignment_id: int
    original_filename: str
    file_path: str
    qwen_file_id: str | None
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

    @field_serializer("due_date")
    def serialize_due_date(self, value: datetime | None) -> str | None:
        return serialize_due_date_as_utc_z(value)


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

    @field_serializer("due_date")
    def serialize_due_date(self, value: datetime | None) -> str | None:
        return serialize_due_date_as_utc_z(value)


class GradeQuestionItem(BaseModel):
    number: int = Field(ge=1)
    is_correct: bool | None
    score: float | None
    max_score: float
    comment: str | None = None


class GradeStartResponse(BaseModel):
    submission_id: int
    status: str


class SubmissionResultResponse(BaseModel):
    submission_id: int
    status: str
    model_name: str
    graded_at: datetime | None
    questions: list[GradeQuestionItem]
    total_score: float
    max_total_score: float


class GradeAllStartResponse(BaseModel):
    assignment_id: int
    total: int
    started: int
    skipped: int


class QuestionOverrideRequest(BaseModel):
    score: float
    is_correct: bool
    comment: str | None = None


class StudentPasswordResetRequest(BaseModel):
    new_password: str = Field(min_length=8)
