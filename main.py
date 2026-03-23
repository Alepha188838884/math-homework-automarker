from __future__ import annotations

import os
import re
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import BinaryIO, Any
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from auth import create_access_token, decode_token, hash_password, verify_password
from database import get_db
from models import AnswerFile, Assignment, Course, GradeResult, Student, Submission, Teacher
from qwen_service import grade_one_submission, upload_file_to_qwen
from runtime_config import get_app_data_dir, get_cors_allow_origins, get_frontend_base_url
from schemas import (
    AnswerFileResponse,
    AssignmentCreate,
    AssignmentOut,
    BootstrapTeacherRequest,
    CourseCreate,
    CourseJoinInfo,
    CourseOut,
    GradeAllFailure,
    GradeAllSummary,
    GradeQuestionItem,
    GradeSubmissionResponse,
    JoinLinkResponse,
    StudentAssignmentStatus,
    StudentCreate,
    StudentEntryRequest,
    StudentJoinRequest,
    StudentJoinResponse,
    StudentLoginRequest,
    StudentLoginResponse,
    StudentPublic,
    SubmissionOut,
    SubmissionResponse,
    SubmissionResultResponse,
    StudentAssignmentOverview,
    TeacherLoginRequest,
    TeacherEntryRequest,
    TeacherLoginResponse,
    TeacherPublic,
)


APP_DATA_DIR = get_app_data_dir()
SOLUTIONS_DIR = APP_DATA_DIR / "solutions"
SUBMISSIONS_DIR = APP_DATA_DIR / "submissions"
TEACHER_CACHE_DIR = APP_DATA_DIR / "teacher"
STUDENT_TMP_DIR = APP_DATA_DIR / "tmp" / "submissions"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/teacher/login")


def _unauthorized(detail: str = "认证失败。") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(detail: str = "无权限访问该资源。") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _get_token_payload(token: str) -> dict[str, Any]:
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise _unauthorized("Token 无效或已过期。") from exc
    return payload


def get_current_teacher(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Teacher:
    payload = _get_token_payload(token)
    role = payload.get("role")
    sub = payload.get("sub")
    if role != "teacher" or sub is None:
        raise _unauthorized("教师认证失败。")
    try:
        teacher_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Token 中用户标识无效。") from exc

    teacher = _get_teacher_by_id(db, teacher_id)
    if teacher is None:
        raise _unauthorized("教师账号不存在。")
    return teacher


def get_current_student(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Student:
    payload = _get_token_payload(token)
    role = payload.get("role")
    sub = payload.get("sub")
    if role != "student" or sub is None:
        raise _unauthorized("学生认证失败。")
    try:
        student_id = int(sub)
    except (TypeError, ValueError) as exc:
        raise _unauthorized("Token 中用户标识无效。") from exc

    student = _get_student_by_id(db, student_id)
    if student is None:
        raise _unauthorized("学生账号不存在。")
    return student


def initialize_app() -> None:
    for target_dir in (
        APP_DATA_DIR,
        SOLUTIONS_DIR,
        SUBMISSIONS_DIR,
        TEACHER_CACHE_DIR,
        STUDENT_TMP_DIR,
    ):
        target_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_app()
    yield


app = FastAPI(
    title="Math Homework Auto-Grading Backend",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allow_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sanitize_filename(filename: str) -> str:
    safe = Path(filename).name
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", safe)
    return safe or "upload.bin"


def save_upload_to_local(upload_file: UploadFile, target_dir: Path) -> Path:
    if not upload_file.filename:
        raise HTTPException(status_code=400, detail="上传文件缺少文件名。")

    safe_name = sanitize_filename(upload_file.filename)
    local_name = f"{uuid4().hex}_{safe_name}"
    local_path = target_dir / local_name

    source: BinaryIO = upload_file.file
    with local_path.open("wb") as buffer:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            if isinstance(chunk, str):
                buffer.write(chunk.encode())
            else:
                buffer.write(chunk)

    return local_path


def _get_course_for_teacher_or_404(db: Session, course_id: int, teacher: Teacher) -> Course:
    course = _get_course_by_id(db, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail=f"Course {course_id} 不存在。")
    if course.teacher_id != teacher.id:
        raise _forbidden("该课程不属于当前老师。")
    return course


def _get_assignment_for_teacher_or_404(db: Session, assignment_id: int, teacher: Teacher) -> Assignment:
    assignment = _get_assignment_by_id(db, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} 不存在。")
    if assignment.teacher_id != teacher.id:
        raise _forbidden("该作业不属于当前老师。")
    return assignment


def _get_submission_for_teacher_or_404(db: Session, submission_id: int, teacher: Teacher) -> Submission:
    submission = _get_submission_by_id(db, submission_id)
    if submission is None:
        raise HTTPException(status_code=404, detail=f"Submission {submission_id} 不存在。")
    assignment = submission.assignment
    if assignment is None or assignment.teacher_id != teacher.id:
        raise _forbidden("该 submission 不属于当前老师。")
    return submission


def _upload_solution_for_assignment(
    db: Session,
    assignment: Assignment,
    file: UploadFile,
) -> AnswerFileResponse:
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="官方答案必须是 .docx 文件。")

    local_path = save_upload_to_local(file, SOLUTIONS_DIR)
    try:
        qwen_file_id = upload_file_to_qwen(str(local_path))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"上传官方答案到 Qwen 失败: {exc}") from exc

    existing = db.execute(
        select(AnswerFile).where(AnswerFile.assignment_id == assignment.id)
    ).scalar_one_or_none()

    if existing:
        existing.original_filename = file.filename
        existing.file_path = str(local_path)
        existing.qwen_file_id = qwen_file_id
        answer_file = existing
    else:
        answer_file = AnswerFile(
            assignment_id=assignment.id,
            original_filename=file.filename,
            file_path=str(local_path),
            qwen_file_id=qwen_file_id,
        )
        db.add(answer_file)

    db.commit()
    db.refresh(answer_file)
    return AnswerFileResponse.model_validate(answer_file)


def _create_submission_with_upload(
    db: Session,
    assignment: Assignment,
    student: Student,
    file: UploadFile,
) -> SubmissionResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="学生作业必须是 .pdf 文件。")
    if student.course_id != assignment.course_id:
        raise HTTPException(status_code=400, detail="student 与 assignment 不属于同一课程。")

    local_path = save_upload_to_local(file, SUBMISSIONS_DIR)

    def clear_grade_result(target: Submission) -> None:
        grade_result = target.grade_result
        if grade_result is None:
            return
        for question in list(grade_result.questions):
            db.delete(question)
        db.flush()
        db.delete(grade_result)

    old_file_paths: list[str] = []
    existing_submissions = (
        db.execute(
            select(Submission)
            .where(
                Submission.assignment_id == assignment.id,
                Submission.student_id == student.id,
            )
            .order_by(Submission.created_at.desc(), Submission.id.desc())
        )
        .scalars()
        .all()
    )

    if existing_submissions:
        # Keep only the latest record and overwrite it with the new upload.
        submission = existing_submissions[0]
        for stale_submission in existing_submissions[1:]:
            old_file_paths.append(stale_submission.file_path)
            clear_grade_result(stale_submission)
            db.delete(stale_submission)

        old_file_paths.append(submission.file_path)
        clear_grade_result(submission)
        submission.original_filename = file.filename
        submission.file_path = str(local_path)
        submission.qwen_file_id = None
        submission.status = "uploaded"
        submission.error_message = None
        submission.graded_at = None
    else:
        submission = Submission(
            assignment_id=assignment.id,
            student_id=student.id,
            original_filename=file.filename,
            file_path=str(local_path),
            status="uploaded",
        )
        db.add(submission)

    db.flush()

    try:
        submission.qwen_file_id = upload_file_to_qwen(str(local_path))
    except Exception as exc:
        submission.status = "failed_upload"
        submission.error_message = f"上传学生文件到 Qwen 失败: {exc}"[:2000]
        db.commit()
        db.refresh(submission)
        raise HTTPException(
            status_code=502,
            detail=f"上传学生文件到 Qwen 失败，submission_id={submission.id}: {exc}",
        ) from exc

    submission.error_message = None
    submission.status = "uploaded"
    db.commit()
    db.refresh(submission)

    # Best effort cleanup for replaced local files.
    for old_path in old_file_paths:
        try:
            old_file = Path(old_path)
            if old_file.exists() and old_file != local_path:
                old_file.unlink()
        except OSError:
            pass

    return SubmissionResponse.model_validate(submission)


def _require_password_match(plain_password: str, password_hash: str) -> None:
    if not verify_password(plain_password, password_hash):
        raise _unauthorized("邮箱或密码错误。")


def _build_teacher_login_response(teacher: Teacher) -> TeacherLoginResponse:
    token = create_access_token({"sub": str(teacher.id), "role": "teacher"})
    return TeacherLoginResponse(
        access_token=token,
        teacher=TeacherPublic.model_validate(teacher),
    )


def _build_student_login_response(student: Student) -> StudentLoginResponse:
    token = create_access_token({"sub": str(student.id), "role": "student"})
    return StudentLoginResponse(
        access_token=token,
        student=StudentPublic.model_validate(student),
    )


def _get_teacher_by_email(db: Session, email: str) -> Teacher | None:
    return db.execute(select(Teacher).where(Teacher.email == email)).scalar_one_or_none()


def _get_student_by_email(db: Session, email: str) -> Student | None:
    return db.execute(select(Student).where(Student.email == email)).scalar_one_or_none()


def _get_teacher_by_id(db: Session, teacher_id: int) -> Teacher | None:
    return db.execute(select(Teacher).where(Teacher.id == teacher_id)).scalar_one_or_none()


def _get_student_by_id(db: Session, student_id: int) -> Student | None:
    return db.execute(select(Student).where(Student.id == student_id)).scalar_one_or_none()


def _get_course_by_id(db: Session, course_id: int) -> Course | None:
    return db.execute(select(Course).where(Course.id == course_id)).scalar_one_or_none()


def _get_course_by_join_token(db: Session, join_token: str) -> Course | None:
    return db.execute(select(Course).where(Course.join_token == join_token)).scalar_one_or_none()


def _get_assignment_by_id(db: Session, assignment_id: int) -> Assignment | None:
    return db.execute(select(Assignment).where(Assignment.id == assignment_id)).scalar_one_or_none()


def _get_submission_by_id(db: Session, submission_id: int) -> Submission | None:
    return db.execute(select(Submission).where(Submission.id == submission_id)).scalar_one_or_none()


def _resolve_course_id_for_student_signup(db: Session, assignment_id: int | None) -> int:
    if assignment_id is not None:
        assignment = _get_assignment_by_id(db, assignment_id)
        if assignment is None:
            raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} 不存在。")
        return assignment.course_id

    course_ids = db.execute(select(Course.id).order_by(Course.id.asc())).scalars().all()
    if len(course_ids) == 1:
        return course_ids[0]
    if len(course_ids) == 0:
        raise HTTPException(status_code=400, detail="系统暂无课程，无法自动注册学生。")
    raise HTTPException(
        status_code=400,
        detail="检测到多个课程，请通过老师提供的 assignmentId 链接完成首次注册。",
    )


def _generate_unique_join_token(db: Session) -> str:
    while True:
        token = secrets.token_urlsafe(32)
        exists = db.execute(select(Course.id).where(Course.join_token == token)).scalar_one_or_none()
        if exists is None:
            return token


def _build_frontend_join_url(token: str) -> str:
    frontend_base = get_frontend_base_url()
    return f"{frontend_base}/student/join/{token}"


def _create_teacher_account(db: Session, *, name: str, email: str, password: str) -> Teacher:
    teacher = Teacher(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )
    db.add(teacher)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="老师邮箱已存在。") from exc
    db.refresh(teacher)
    return teacher


def _create_student_account(
    db: Session,
    *,
    name: str,
    email: str,
    course_id: int,
    password: str,
) -> Student:
    student = Student(
        name=name,
        email=email,
        course_id=course_id,
        password_hash=hash_password(password),
    )
    db.add(student)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="学生邮箱已存在。") from exc
    db.refresh(student)
    return student


def _get_latest_submission(
    db: Session,
    *,
    assignment_id: int,
    student_id: int,
) -> Submission | None:
    return (
        db.execute(
            select(Submission)
            .where(
                Submission.assignment_id == assignment_id,
                Submission.student_id == student_id,
            )
            .order_by(Submission.created_at.desc(), Submission.id.desc())
        )
        .scalars()
        .first()
    )


def _extract_submission_metrics(
    latest_submission: Submission | None,
) -> tuple[bool, int | None, str | None, float | None, float | None]:
    has_submitted = latest_submission is not None
    if latest_submission is None:
        return False, None, None, None, None

    submission_id = latest_submission.id
    submission_status = latest_submission.status
    grade_result = latest_submission.grade_result
    if grade_result is None:
        return has_submitted, submission_id, submission_status, None, None

    return (
        has_submitted,
        submission_id,
        submission_status,
        grade_result.total_score,
        grade_result.max_total_score,
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/bootstrap-teacher", response_model=TeacherLoginResponse)
def bootstrap_teacher(
    payload: BootstrapTeacherRequest,
    db: Session = Depends(get_db),
) -> TeacherLoginResponse:
    teacher_count = int(db.scalar(select(func.count(Teacher.id))) or 0)
    if teacher_count > 0:
        raise HTTPException(status_code=400, detail="系统已存在老师账号，bootstrap 已关闭。")

    teacher = _create_teacher_account(
        db,
        name=payload.name,
        email=payload.email,
        password=payload.password,
    )

    return _build_teacher_login_response(teacher)


@app.post("/auth/teacher/login", response_model=TeacherLoginResponse)
def teacher_login(
    payload: TeacherLoginRequest,
    db: Session = Depends(get_db),
) -> TeacherLoginResponse:
    teacher = _get_teacher_by_email(db, payload.email)
    if teacher is None:
        raise _unauthorized("邮箱或密码错误。")
    _require_password_match(payload.password, teacher.password_hash)
    return _build_teacher_login_response(teacher)


@app.post("/auth/teacher/entry", response_model=TeacherLoginResponse)
def teacher_entry(
    payload: TeacherEntryRequest,
    db: Session = Depends(get_db),
) -> TeacherLoginResponse:
    teacher = _get_teacher_by_email(db, payload.email)

    if teacher is not None:
        _require_password_match(payload.password, teacher.password_hash)
        return _build_teacher_login_response(teacher)

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="新账号注册需要提供 name。")

    teacher = _create_teacher_account(
        db,
        name=name,
        email=payload.email,
        password=payload.password,
    )

    return _build_teacher_login_response(teacher)


@app.post("/auth/student/login", response_model=StudentLoginResponse)
def student_login(
    payload: StudentLoginRequest,
    db: Session = Depends(get_db),
) -> StudentLoginResponse:
    student = _get_student_by_email(db, payload.email)
    if student is None:
        raise _unauthorized("邮箱或密码错误。")
    _require_password_match(payload.password, student.password_hash)
    return _build_student_login_response(student)


@app.post("/auth/student/entry", response_model=StudentLoginResponse)
def student_entry(
    payload: StudentEntryRequest,
    db: Session = Depends(get_db),
) -> StudentLoginResponse:
    student = _get_student_by_email(db, payload.email)

    if student is not None:
        _require_password_match(payload.password, student.password_hash)
        return _build_student_login_response(student)

    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="新账号注册需要提供 name。")
    course_id = _resolve_course_id_for_student_signup(db, payload.assignment_id)

    student = _create_student_account(
        db,
        name=name,
        email=payload.email,
        course_id=course_id,
        password=payload.password,
    )

    return _build_student_login_response(student)


@app.post("/teachers/me/courses", response_model=CourseOut)
def create_course_for_teacher(
    payload: CourseCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> CourseOut:
    course = Course(
        teacher_id=current_teacher.id,
        name=payload.name,
        description=payload.description,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return CourseOut.model_validate(course)


@app.get("/teachers/me/courses", response_model=list[CourseOut])
def list_my_courses(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[CourseOut]:
    courses = (
        db.execute(
            select(Course)
            .where(Course.teacher_id == current_teacher.id)
            .order_by(Course.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [CourseOut.model_validate(item) for item in courses]


@app.post("/courses/{course_id}/join-link", response_model=JoinLinkResponse)
def generate_course_join_link(
    course_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> JoinLinkResponse:
    course = _get_course_for_teacher_or_404(db, course_id, current_teacher)
    join_token = _generate_unique_join_token(db)
    course.join_token = join_token
    db.commit()
    db.refresh(course)
    return JoinLinkResponse(
        course_id=course.id,
        join_token=join_token,
        join_url=_build_frontend_join_url(join_token),
    )


@app.get("/courses/join/{join_token}", response_model=CourseJoinInfo)
def get_course_join_info(
    join_token: str,
    db: Session = Depends(get_db),
) -> CourseJoinInfo:
    course = _get_course_by_join_token(db, join_token)
    if course is None:
        raise HTTPException(status_code=404, detail="链接无效或班级不存在。")
    teacher_name = course.teacher.name if course.teacher is not None else None
    return CourseJoinInfo(
        course_id=course.id,
        course_name=course.name,
        teacher_name=teacher_name,
    )


@app.post(
    "/courses/join/{join_token}/register",
    response_model=StudentJoinResponse,
    status_code=201,
)
def register_student_via_join_link(
    join_token: str,
    payload: StudentJoinRequest,
    db: Session = Depends(get_db),
) -> StudentJoinResponse:
    course = _get_course_by_join_token(db, join_token)
    if course is None:
        raise HTTPException(status_code=404, detail="链接无效或班级不存在。")

    student = _create_student_account(
        db,
        name=payload.name,
        email=payload.email,
        course_id=course.id,
        password=payload.password,
    )
    return StudentJoinResponse(
        student_id=student.id,
        course_id=student.course_id,
        email=student.email,
        access_token=None,
        token_type=None,
    )


@app.get("/courses/{course_id}/students", response_model=list[StudentPublic])
def list_course_students(
    course_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[StudentPublic]:
    _get_course_for_teacher_or_404(db, course_id, current_teacher)
    students = (
        db.execute(
            select(Student)
            .where(Student.course_id == course_id)
            .order_by(Student.created_at.asc())
        )
        .scalars()
        .all()
    )
    return [StudentPublic.model_validate(item) for item in students]


@app.post("/courses/{course_id}/students", response_model=StudentPublic)
def create_student_for_course(
    course_id: int,
    payload: StudentCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> StudentPublic:
    _get_course_for_teacher_or_404(db, course_id, current_teacher)
    student = _create_student_account(
        db,
        name=payload.name,
        email=payload.email,
        course_id=course_id,
        password=payload.password,
    )
    return StudentPublic.model_validate(student)


@app.post("/courses/{course_id}/assignments", response_model=AssignmentOut)
def create_assignment_for_course(
    course_id: int,
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> AssignmentOut:
    _get_course_for_teacher_or_404(db, course_id, current_teacher)
    max_score_value = payload.max_score if payload.max_score is not None else 100.0
    if max_score_value <= 0:
        raise HTTPException(status_code=400, detail="max_score 必须大于 0。")

    assignment = Assignment(
        teacher_id=current_teacher.id,
        course_id=course_id,
        title=payload.title,
        description=payload.description,
        due_date=payload.due_date,
        max_score=max_score_value,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return AssignmentOut.model_validate(assignment)


@app.get("/courses/{course_id}/assignments", response_model=list[AssignmentOut])
def list_assignments_for_course(
    course_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[AssignmentOut]:
    _get_course_for_teacher_or_404(db, course_id, current_teacher)
    assignments = (
        db.execute(
            select(Assignment)
            .where(Assignment.course_id == course_id)
            .order_by(Assignment.created_at.desc(), Assignment.id.desc())
        )
        .scalars()
        .all()
    )
    return [AssignmentOut.model_validate(item) for item in assignments]


@app.post(
    "/teachers/{teacher_id}/assignments/{assignment_id}/solution",
    response_model=AnswerFileResponse,
)
def upload_solution_file_legacy_path(
    teacher_id: int,
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> AnswerFileResponse:
    if teacher_id != current_teacher.id:
        raise _forbidden("teacher_id 与当前登录老师不一致。")
    assignment = _get_assignment_for_teacher_or_404(db, assignment_id, current_teacher)
    return _upload_solution_for_assignment(db, assignment, file)


@app.post("/assignments/{assignment_id}/solution", response_model=AnswerFileResponse)
def upload_solution_file(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> AnswerFileResponse:
    assignment = _get_assignment_for_teacher_or_404(db, assignment_id, current_teacher)
    return _upload_solution_for_assignment(db, assignment, file)


@app.post(
    "/assignments/{assignment_id}/submissions",
    response_model=SubmissionResponse,
    status_code=201,
)
def upload_student_submission_by_teacher(
    assignment_id: int,
    student_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> SubmissionResponse:
    assignment = _get_assignment_for_teacher_or_404(db, assignment_id, current_teacher)
    student = _get_student_by_id(db, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail=f"Student {student_id} 不存在。")
    return _create_submission_with_upload(db, assignment, student, file)


@app.post(
    "/assignments/{assignment_id}/submissions/me",
    response_model=SubmissionResponse,
    status_code=201,
)
def upload_student_submission_me(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
) -> SubmissionResponse:
    assignment = _get_assignment_by_id(db, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail=f"Assignment {assignment_id} 不存在。")
    if current_student.course_id != assignment.course_id:
        raise _forbidden("当前学生不属于该作业所在课程。")
    return _create_submission_with_upload(db, assignment, current_student, file)


@app.post("/submissions/{submission_id}/grade", response_model=GradeSubmissionResponse)
def grade_single_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> GradeSubmissionResponse:
    _get_submission_for_teacher_or_404(db, submission_id, current_teacher)
    return grade_one_submission(db, submission_id)


@app.get("/assignments", response_model=list[AssignmentOut])
def list_assignments(
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[AssignmentOut]:
    assignments = (
        db.execute(
            select(Assignment)
            .where(Assignment.teacher_id == current_teacher.id)
            .order_by(Assignment.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [AssignmentOut.model_validate(item) for item in assignments]


@app.get("/assignments/{assignment_id}/submissions", response_model=list[SubmissionOut])
def list_assignment_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[SubmissionOut]:
    _get_assignment_for_teacher_or_404(db, assignment_id, current_teacher)
    submissions = (
        db.execute(
            select(Submission)
            .where(Submission.assignment_id == assignment_id)
            .order_by(Submission.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [SubmissionOut.model_validate(item) for item in submissions]


@app.get(
    "/assignments/{assignment_id}/students-status",
    response_model=list[StudentAssignmentStatus],
)
def list_assignment_student_status(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> list[StudentAssignmentStatus]:
    assignment = _get_assignment_for_teacher_or_404(db, assignment_id, current_teacher)

    students = (
        db.execute(
            select(Student)
            .where(Student.course_id == assignment.course_id)
            .order_by(Student.created_at.asc())
        )
        .scalars()
        .all()
    )

    result: list[StudentAssignmentStatus] = []
    for student in students:
        latest_submission = _get_latest_submission(
            db,
            assignment_id=assignment.id,
            student_id=student.id,
        )
        has_submitted, submission_id, submission_status, total_score, max_total_score = (
            _extract_submission_metrics(latest_submission)
        )

        result.append(
            StudentAssignmentStatus(
                student_id=student.id,
                student_name=student.name,
                student_email=student.email,
                has_submitted=has_submitted,
                submission_id=submission_id,
                submission_status=submission_status,
                total_score=total_score,
                max_total_score=max_total_score,
            )
        )

    return result


@app.get("/students/me/assignments", response_model=list[StudentAssignmentOverview])
def list_my_assignments_overview(
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
) -> list[StudentAssignmentOverview]:
    assignments = (
        db.execute(
            select(Assignment)
            .where(Assignment.course_id == current_student.course_id)
            .order_by(Assignment.created_at.desc(), Assignment.id.desc())
        )
        .scalars()
        .all()
    )

    overview: list[StudentAssignmentOverview] = []
    for assignment in assignments:
        latest_submission = _get_latest_submission(
            db,
            assignment_id=assignment.id,
            student_id=current_student.id,
        )
        has_submitted, submission_id, submission_status, total_score, max_total_score = (
            _extract_submission_metrics(latest_submission)
        )

        overview.append(
            StudentAssignmentOverview(
                assignment_id=assignment.id,
                title=assignment.title,
                description=assignment.description,
                created_at=assignment.created_at,
                due_date=assignment.due_date,
                max_score=assignment.max_score,
                has_submitted=has_submitted,
                submission_id=submission_id,
                submission_status=submission_status,
                total_score=total_score,
                max_total_score=max_total_score,
            )
        )

    return overview


@app.post("/assignments/{assignment_id}/grade-all", response_model=GradeAllSummary)
def grade_all_submissions(
    assignment_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> GradeAllSummary:
    _get_assignment_for_teacher_or_404(db, assignment_id, current_teacher)

    all_count = int(
        db.scalar(select(func.count(Submission.id)).where(Submission.assignment_id == assignment_id))
        or 0
    )

    candidates = (
        db.execute(
            select(Submission).where(
                Submission.assignment_id == assignment_id,
                Submission.status != "graded",
            )
        )
        .scalars()
        .all()
    )

    failures: list[GradeAllFailure] = []
    graded_count = 0
    failed_count = 0

    for submission in candidates:
        try:
            _get_submission_for_teacher_or_404(db, submission.id, current_teacher)
            grade_one_submission(db, submission.id)
            graded_count += 1
        except HTTPException as exc:
            failed_count += 1
            failures.append(GradeAllFailure(submission_id=submission.id, detail=str(exc.detail)))
        except Exception as exc:
            failed_count += 1
            failures.append(GradeAllFailure(submission_id=submission.id, detail=str(exc)))

    return GradeAllSummary(
        assignment_id=assignment_id,
        total=len(candidates),
        graded=graded_count,
        failed=failed_count,
        skipped=int(all_count) - len(candidates),
        failures=failures,
    )


@app.get("/submissions/{submission_id}/result", response_model=SubmissionResultResponse)
def get_submission_result(
    submission_id: int,
    db: Session = Depends(get_db),
    current_teacher: Teacher = Depends(get_current_teacher),
) -> SubmissionResultResponse:
    submission = _get_submission_for_teacher_or_404(db, submission_id, current_teacher)
    if submission.status not in {"graded", "needs_manual_review"}:
        raise HTTPException(status_code=404, detail="该 submission 尚未完成评分。")

    grade_result = db.execute(
        select(GradeResult).where(GradeResult.submission_id == submission_id)
    ).scalar_one_or_none()
    if grade_result is None:
        raise HTTPException(status_code=404, detail="该 submission 尚无评分结果。")

    questions: list[GradeQuestionItem] = []
    raw_json = grade_result.raw_json if isinstance(grade_result.raw_json, dict) else {}
    normalized = raw_json.get("normalized") if isinstance(raw_json, dict) else None
    normalized_questions = normalized.get("questions") if isinstance(normalized, dict) else None
    if isinstance(normalized_questions, list):
        for index, item in enumerate(normalized_questions, start=1):
            if not isinstance(item, dict):
                continue
            question_id = str(item.get("question_id") or f"Q{index}").strip() or f"Q{index}"
            question_number_raw = item.get("question_number", index)
            question_number = int(question_number_raw) if isinstance(question_number_raw, int) else index
            comment = str(item.get("comment") or "").strip() or None
            auto_graded = bool(item.get("auto_graded", False))
            if not auto_graded and comment and "人工复核" not in comment:
                comment = f"{comment}（需人工复核）"
            if comment and not comment.startswith("["):
                comment = f"[{question_id}] {comment}"
            score_raw = item.get("score")
            score = float(score_raw) if isinstance(score_raw, (int, float)) else None
            is_correct_raw = item.get("is_correct")
            is_correct = bool(is_correct_raw) if isinstance(is_correct_raw, bool) else None
            max_score_raw = item.get("max_score")
            max_score = float(max_score_raw) if isinstance(max_score_raw, (int, float)) else 1.0
            questions.append(
                GradeQuestionItem(
                    number=question_number,
                    is_correct=is_correct,
                    score=score,
                    max_score=max_score,
                    comment=comment,
                )
            )
    else:
        questions = [
            GradeQuestionItem(
                number=item.question_number,
                is_correct=item.is_correct,
                score=item.score,
                max_score=item.max_score,
                comment=item.comment,
            )
            for item in grade_result.questions
        ]
    return SubmissionResultResponse(
        submission_id=submission_id,
        status=submission.status,
        model_name=grade_result.model_name,
        graded_at=submission.graded_at,
        questions=questions,
        total_score=grade_result.total_score,
        max_total_score=grade_result.max_total_score,
    )


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() == "true"
    uvicorn.run("main:app", host=host, port=port, reload=reload_enabled)
