import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import AdminApp from "./AdminApp.jsx";
import { AdminAuthProvider } from "./adminAuth.jsx";
import { DialogProvider } from "./components/Dialog.jsx";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter basename="/admin">
      <DialogProvider>
        <AdminAuthProvider>
          <AdminApp />
        </AdminAuthProvider>
      </DialogProvider>
    </BrowserRouter>
  </React.StrictMode>
);
