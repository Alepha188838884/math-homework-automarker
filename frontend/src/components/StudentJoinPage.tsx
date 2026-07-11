import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { type CourseJoinInfo, fetchCourseJoinInfo, registerStudentViaJoinToken } from "../api";
import { getErrorMessage, type StatusMessage } from "../utils";

function isLikelyValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function StudentJoinPage() {
  const navigate = useNavigate();
  const { joinToken } = useParams<{ joinToken: string }>();

  const [courseInfo, setCourseInfo] = useState<CourseJoinInfo | null>(null);
  const [isLoadingInfo, setIsLoadingInfo] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);
  const [isTokenInvalid, setIsTokenInvalid] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  useEffect(() => {
    const token = (joinToken ?? "").trim();
    if (!token) {
      setIsTokenInvalid(true);
      setMessage({ type: "error", text: "链接无效或班级不存在。" });
      setIsLoadingInfo(false);
      return;
    }
    const run = async () => {
      setIsLoadingInfo(true);
      setMessage(null);
      try {
        const info = await fetchCourseJoinInfo(token);
        setCourseInfo(info);
        setIsTokenInvalid(false);
      } catch (error) {
        setCourseInfo(null);
        setIsTokenInvalid(true);
        setMessage({
          type: "error",
          text: getErrorMessage(error).includes("HTTP 404") ? "链接无效或班级不存在。" : getErrorMessage(error),
        });
      } finally {
        setIsLoadingInfo(false);
      }
    };
    void run();
  }, [joinToken]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const token = (joinToken ?? "").trim();
    if (!token || isTokenInvalid) { setMessage({ type: "error", text: "链接无效，无法注册。" }); return; }
    if (!name.trim() || !email.trim() || !password) { setMessage({ type: "error", text: "请完整填写姓名、邮箱和密码。" }); return; }
    if (!isLikelyValidEmail(email.trim())) { setMessage({ type: "error", text: "邮箱格式不正确，请填写如 name@example.com。" }); return; }

    setIsSubmitting(true);
    setMessage(null);
    try {
      await registerStudentViaJoinToken(token, { name: name.trim(), email: email.trim(), password });
      setMessage({ type: "success", text: "注册成功，请前往学生登录页登录。" });
      window.setTimeout(() => navigate("/student/login", { replace: true }), 800);
    } catch (error) {
      setMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="card card-narrow login-card">
      <h2 className="section-title">学生加入班级</h2>
      {isLoadingInfo ? (
        <div className="alert alert-info">正在校验加入链接...</div>
      ) : isTokenInvalid ? (
        <div className="alert alert-error">链接无效或班级不存在，请向老师获取最新加入链接。</div>
      ) : (
        <>
          <div className="alert alert-info">
            你正在加入班级：<strong>{courseInfo?.course_name}</strong>
            {courseInfo?.teacher_name ? `（老师：${courseInfo.teacher_name}）` : ""}
          </div>
          <form onSubmit={handleSubmit} className="form-stack" style={{ marginTop: "14px" }}>
            <label className="form-group">
              <span className="form-label">姓名</span>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="form-input" required />
            </label>
            <label className="form-group">
              <span className="form-label">邮箱</span>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} className="form-input" required />
            </label>
            <label className="form-group">
              <span className="form-label">密码</span>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} className="form-input" required />
            </label>
            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? "注册中..." : "注册并加入班级"}
            </button>
          </form>
        </>
      )}
      {message && <div className={`alert alert-${message.type}`}>{message.text}</div>}
    </section>
  );
}

export default StudentJoinPage;
