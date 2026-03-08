import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTeacherAuth } from "../auth/TeacherAuthContext";

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function TeacherLoginPage() {
  const navigate = useNavigate();
  const { ready, isAuthenticated, loginTeacher } = useTeacherAuth();

  const [name, setName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [rememberMe, setRememberMe] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate("/teacher", { replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      setIsLoading(true);
      await loginTeacher({
        email: email.trim(),
        password,
        name: name.trim() || undefined,
        rememberMe,
      });
      navigate("/teacher", { replace: true });
    } catch (error) {
      setMessage(getErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section style={cardStyle}>
      <h2 style={titleStyle}>教师登录 / 注册</h2>
      <p style={hintStyle}>
        系统会自动识别账号：邮箱已存在则登录，不存在则自动注册。默认记住登录状态。
      </p>
      <form onSubmit={handleSubmit} style={formStyle}>
        <label style={fieldStyle}>
          <span>Name（新账号必填）</span>
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            style={inputStyle}
            placeholder="首次注册时填写"
          />
        </label>
        <label style={fieldStyle}>
          <span>Email</span>
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
            style={inputStyle}
          />
        </label>
        <label style={fieldStyle}>
          <span>Password</span>
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            style={inputStyle}
          />
        </label>
        <label style={rememberRowStyle}>
          <input
            type="checkbox"
            checked={rememberMe}
            onChange={(event) => setRememberMe(event.target.checked)}
          />
          <span>Remember me</span>
        </label>
        <button type="submit" disabled={isLoading} style={buttonStyle}>
          {isLoading ? "Processing..." : "Continue"}
        </button>
        {message && <div style={errorStyle}>{message}</div>}
      </form>
    </section>
  );
}

const cardStyle: React.CSSProperties = {
  backgroundColor: "#ffffff",
  border: "1px solid #e2e8f0",
  borderRadius: "14px",
  padding: "16px",
  boxShadow: "0 6px 18px rgba(15, 23, 42, 0.06)",
  maxWidth: "460px",
};

const titleStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "8px",
  color: "#0f172a",
};

const hintStyle: React.CSSProperties = {
  marginTop: 0,
  marginBottom: "12px",
  color: "#475569",
  fontSize: "0.92rem",
};

const formStyle: React.CSSProperties = {
  display: "grid",
  gap: "10px",
};

const fieldStyle: React.CSSProperties = {
  display: "grid",
  gap: "6px",
  color: "#334155",
  fontSize: "0.92rem",
};

const inputStyle: React.CSSProperties = {
  border: "1px solid #cbd5e1",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.95rem",
};

const rememberRowStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  fontSize: "0.9rem",
  color: "#334155",
};

const buttonStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "9px 12px",
  cursor: "pointer",
};

const errorStyle: React.CSSProperties = {
  color: "#991b1b",
  backgroundColor: "#fee2e2",
  border: "1px solid #fca5a5",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.9rem",
};

export default TeacherLoginPage;
