import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useStudentAuth } from "../auth/StudentAuthContext";
import { getErrorMessage } from "../utils";

function StudentLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { ready, isAuthenticated, loginStudent } = useStudentAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (ready && isAuthenticated) navigate(`/student${location.search}`, { replace: true });
  }, [ready, isAuthenticated, navigate, location.search]);

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      setIsLoading(true);
      await loginStudent({ email: email.trim(), password, rememberMe });
      navigate(`/student${location.search}`, { replace: true });
    } catch (error) {
      const text = getErrorMessage(error);
      setMessage(text.includes("HTTP 401")
        ? "登录失败：账号或密码错误。如果你是首次使用，请先通过老师提供的班级加入链接完成注册。"
        : text);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="card card-narrow login-card">
      <h2 className="section-title">学生登录</h2>
      <p className="hint">
        推荐先通过老师提供的「班级加入链接」完成首次注册；这里用于已有账号登录。
      </p>
      <div className="login-warn">首次注册请使用老师提供的班级加入链接。</div>
      <form onSubmit={handleLogin} className="form-stack">
        <label className="form-group">
          <span className="form-label">邮箱</span>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className="form-input" />
        </label>
        <label className="form-group">
          <span className="form-label">密码</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className="form-input" />
        </label>
        <label className="remember-row">
          <input type="checkbox" checked={rememberMe} onChange={(e) => setRememberMe(e.target.checked)} />
          <span>记住登录</span>
        </label>
        <button type="submit" disabled={isLoading} className="btn btn-primary">
          {isLoading ? "登录中..." : "登录"}
        </button>
        {message && <div className="alert alert-error">{message}</div>}
      </form>
    </section>
  );
}

export default StudentLoginPage;
