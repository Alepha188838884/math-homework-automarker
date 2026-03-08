import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  type CourseJoinInfo,
  fetchCourseJoinInfo,
  registerStudentViaJoinToken,
} from "../api";

type MessageType = "success" | "error" | "info";

interface StatusMessage {
  type: MessageType;
  text: string;
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return "Unknown error";
}

function isLikelyValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function messageStyle(type: MessageType): React.CSSProperties {
  if (type === "success") {
    return {
      color: "#166534",
      backgroundColor: "#dcfce7",
      border: "1px solid #86efac",
    };
  }
  if (type === "error") {
    return {
      color: "#991b1b",
      backgroundColor: "#fee2e2",
      border: "1px solid #fca5a5",
    };
  }
  return {
    color: "#1e3a8a",
    backgroundColor: "#dbeafe",
    border: "1px solid #93c5fd",
  };
}

function StudentJoinPage() {
  const navigate = useNavigate();
  const { joinToken } = useParams<{ joinToken: string }>();

  const [courseInfo, setCourseInfo] = useState<CourseJoinInfo | null>(null);
  const [isLoadingInfo, setIsLoadingInfo] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [message, setMessage] = useState<StatusMessage | null>(null);
  const [isTokenInvalid, setIsTokenInvalid] = useState<boolean>(false);

  const [name, setName] = useState<string>("");
  const [email, setEmail] = useState<string>("");
  const [password, setPassword] = useState<string>("");

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
          text: getErrorMessage(error).includes("HTTP 404")
            ? "链接无效或班级不存在。"
            : getErrorMessage(error),
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
    if (!token || isTokenInvalid) {
      setMessage({ type: "error", text: "链接无效，无法注册。" });
      return;
    }

    if (!name.trim() || !email.trim() || !password) {
      setMessage({ type: "error", text: "请完整填写姓名、邮箱和密码。" });
      return;
    }
    if (!isLikelyValidEmail(email.trim())) {
      setMessage({ type: "error", text: "邮箱格式不正确，请填写如 name@example.com。" });
      return;
    }

    setIsSubmitting(true);
    setMessage(null);
    try {
      await registerStudentViaJoinToken(token, {
        name: name.trim(),
        email: email.trim(),
        password,
      });
      setMessage({ type: "success", text: "注册成功，请前往学生登录页登录。" });
      window.setTimeout(() => {
        navigate("/student/login", { replace: true });
      }, 800);
    } catch (error) {
      setMessage({ type: "error", text: getErrorMessage(error) });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section style={cardStyle}>
      <h2 style={titleStyle}>学生加入班级</h2>
      {isLoadingInfo ? (
        <div style={{ ...alertStyle, ...messageStyle("info") }}>正在校验加入链接...</div>
      ) : isTokenInvalid ? (
        <div style={{ ...alertStyle, ...messageStyle("error") }}>
          链接无效或班级不存在，请向老师获取最新加入链接。
        </div>
      ) : (
        <>
          <div style={{ ...alertStyle, ...messageStyle("info") }}>
            你正在加入班级：<strong>{courseInfo?.course_name}</strong>
            {courseInfo?.teacher_name ? `（老师：${courseInfo.teacher_name}）` : ""}
          </div>
          <form onSubmit={handleSubmit} style={formStyle}>
            <label style={fieldStyle}>
              <span>Name</span>
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                style={inputStyle}
                required
              />
            </label>
            <label style={fieldStyle}>
              <span>Email</span>
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                style={inputStyle}
                required
              />
            </label>
            <label style={fieldStyle}>
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                style={inputStyle}
                required
              />
            </label>
            <button type="submit" style={buttonStyle} disabled={isSubmitting}>
              {isSubmitting ? "Registering..." : "注册并加入班级"}
            </button>
          </form>
        </>
      )}
      {message && (
        <div style={{ ...alertStyle, ...messageStyle(message.type) }}>{message.text}</div>
      )}
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
  marginBottom: "12px",
  color: "#0f172a",
};

const formStyle: React.CSSProperties = {
  display: "grid",
  gap: "10px",
  marginTop: "10px",
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

const buttonStyle: React.CSSProperties = {
  border: "none",
  borderRadius: "8px",
  backgroundColor: "#2563eb",
  color: "#ffffff",
  padding: "9px 12px",
  cursor: "pointer",
};

const alertStyle: React.CSSProperties = {
  borderRadius: "8px",
  padding: "8px 10px",
  fontSize: "0.9rem",
  marginTop: "10px",
};

export default StudentJoinPage;
