import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useStudentAuth } from "../auth/StudentAuthContext";

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function StudentLoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { ready, isAuthenticated, loginStudent } = useStudentAuth();
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");
  const [rememberMe, setRememberMe] = useState<boolean>(true);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [message, setMessage] = useState<string>("");

  useEffect(() => {
    if (ready && isAuthenticated) {
      navigate(`/student${location.search}`, { replace: true });
    }
  }, [ready, isAuthenticated, navigate, location.search]);

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage("");
    try {
      setIsLoading(true);
      await loginStudent({
        email: email.trim(),
        password,
        rememberMe,
      });
      navigate(`/student${location.search}`, { replace: true });
    } catch (error) {
      const text = getErrorMessage(error);
      if (text.includes("HTTP 401")) {
        setMessage(
          "登录失败：账号或密码错误。如果你是首次使用，请先通过老师提供的班级加入链接完成注册。",
        );
      } else {
        setMessage(text);
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <section style={cardStyle}>
      <h2 style={titleStyle}>学生登录 / 注册</h2>
      <p style={hintStyle}>
        推荐先通过老师提供的“班级加入链接”完成首次注册；这里用于已有账号登录。
      </p>
      <div style={warnStyle}>首次注册请使用老师提供的班级加入链接。</div>
      <form onSubmit={handleLogin} style={formStyle}>
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
  marginBottom: "10px",
  color: "#475569",
  fontSize: "0.92rem",
};

const warnStyle: React.CSSProperties = {
  color: "#7c2d12",
  backgroundColor: "#ffedd5",
  border: "1px solid #fdba74",
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.9rem",
  marginBottom: "10px",
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

export default StudentLoginPage;
