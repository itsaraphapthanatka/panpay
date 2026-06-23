import { createContext, useContext, useEffect, useState } from "react";
import { api, setToken, getToken } from "./api";

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [merchant, setMerchant] = useState(null);
  const [loading, setLoading] = useState(true);

  async function refresh() {
    if (!getToken()) {
      setMerchant(null);
      setLoading(false);
      return;
    }
    try {
      setMerchant(await api.me());
    } catch {
      setToken(null);
      setMerchant(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function login(email, password) {
    const { access_token } = await api.login({ email, password });
    setToken(access_token);
    await refresh();
  }

  async function register(body) {
    const { access_token } = await api.register(body);
    setToken(access_token);
    await refresh();
  }

  function logout() {
    setToken(null);
    setMerchant(null);
  }

  return (
    <AuthCtx.Provider value={{ merchant, loading, login, register, logout, refresh }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
