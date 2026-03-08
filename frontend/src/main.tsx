import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { StudentAuthProvider } from "./auth/StudentAuthContext";
import { TeacherAuthProvider } from "./auth/TeacherAuthContext";

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <TeacherAuthProvider>
      <StudentAuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </StudentAuthProvider>
    </TeacherAuthProvider>
  </React.StrictMode>,
);
