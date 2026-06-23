import { createContext, useContext, useEffect, useState } from "react";
import { adminApi, getAdminToken, setAdminToken } from "./api";

const AdminAuthCtx = createContext(null);

export function AdminAuthProvider({ children }) {
  const [admin, setAdmin] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!getAdminToken()) {
      setAdmin(null);
      setLoading(false);
      return;
    }
    try {
      setAdmin(await adminApi.me());
    } catch {
      setAdminToken(null);
      setAdmin(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function login(email, password) {
    const { access_token } = await adminApi.login({ email, password });
    setAdminToken(access_token);
    await refresh();
  }

  function logout() {
    setAdminToken(null);
    setAdmin(null);
  }

  return (
    <AdminAuthCtx.Provider value={{ admin, loading, login, logout, refresh }}>
      {children}
    </AdminAuthCtx.Provider>
  );
}

export const useAdminAuth = () => useContext(AdminAuthCtx);
