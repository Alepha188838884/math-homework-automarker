import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTeacherAuth } from "../auth/TeacherAuthContext";
import { getErrorMessage } from "../utils";

function TeacherLoginPage() {
  const navigate = useNavigate();
  const { ready, isAuthenticated, loginTeacher } = useTeacherAuth();

  const [name, setName] = useState("");
  const [signupCode, setSignupCode] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (ready && isAuthenticated) navigate("/teacher", { replace: true });
  }, [ready, isAuthenticated, navigate]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      setIsLoading(true);
      await loginTeacher({ email: email.trim(), password, name: name.trim() || undefined, signupCode: signupCode.trim() || undefined, rememberMe });
      navigate("/teacher", { replace: true });
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section className="card card-narrow login-card">
      <h2 className="section-title">教师登录 / 注册</h2>
      <p className="hint">
        系统会自动识别账号：邮箱已存在则登录，不存在则自动注册。默认记住登录状态。
      </p>
      <form onSubmit={handleSubmit} className="form-stack">
        <label className="form-group">
          <span className="form-label">姓名（新账号必填）</span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} className="form-input" placeholder="首次注册时填写" />
        </label>
        {name.trim() && (
          <label className="form-group">
            <span className="form-label">邀请码（如老师提供，选填）</span>
            <input type="text" value={signupCode} onChange={(e) => setSignupCode(e.target.value)} className="form-input" placeholder="仅新注册教师账号需要" />
          </label>
        )}
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
          {isLoading ? "登录中..." : "登录 / 注册"}
        </button>
        {message && <div className="alert alert-error">{message}</div>}
      </form>
    </section>
  );
}

export default TeacherLoginPage;
