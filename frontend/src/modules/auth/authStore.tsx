import * as React from "react";

import {
  fetchCurrentUser,
  loginWithCredentials,
  logoutSession,
  type PortalPermissionKey,
  type PortalUser,
} from "@/modules/auth/authApi";
import { clearStoredToken, getStoredToken, setStoredToken } from "@/modules/auth/authStorage";

interface AuthContextValue {
  user: PortalUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<PortalUser>;
  logout: () => Promise<void>;
  hasPermission: (permission: PortalPermissionKey) => boolean;
}

const AuthContext = React.createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setToken] = React.useState<string | null>(() => getStoredToken());
  const [user, setUser] = React.useState<PortalUser | null>(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    let active = true;

    async function loadUser() {
      if (!token) {
        setLoading(false);
        return;
      }

      try {
        const currentUser = await fetchCurrentUser();
        if (active) setUser(currentUser);
      } catch {
        clearStoredToken();
        if (active) {
          setToken(null);
          setUser(null);
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    setLoading(true);
    void loadUser();

    return () => {
      active = false;
    };
  }, [token]);

  async function login(username: string, password: string) {
    const response = await loginWithCredentials(username, password);
    setStoredToken(response.access_token);
    setToken(response.access_token);
    setUser(response.user);
    return response.user;
  }

  async function logout() {
    try {
      await logoutSession();
    } finally {
      clearStoredToken();
      setToken(null);
      setUser(null);
    }
  }

  function hasPermission(permission: PortalPermissionKey) {
    return Boolean(user?.permissions[permission]);
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout, hasPermission }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = React.useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth deve ser usado dentro de AuthProvider");
  }

  return context;
}

