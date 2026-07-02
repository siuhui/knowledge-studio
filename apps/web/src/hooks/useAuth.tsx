"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, resetUnauthorizedFlag } from "@/lib/api";
import { getToken, removeToken, setToken } from "@/lib/auth";

interface User {
  id: string;
  username: string;
}

interface AuthContextValue {
  user: User | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check for existing session on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setIsLoading(false);
      return;
    }
    // Try to get current user info — skip for now (no /me endpoint in v0.1)
    // Just trust the token and set a placeholder
    setUser({ id: "", username: "" });
    setIsLoading(false);
  }, []);

  // Listen for global 401 unauthorized events fired by the api layer
  useEffect(() => {
    const handler = () => {
      removeToken();
      setUser(null);
      router.replace("/login");
    };
    window.addEventListener("auth:unauthorized", handler);
    return () => window.removeEventListener("auth:unauthorized", handler);
  }, [router]);

  const login = useCallback(async (username: string, password: string) => {
    const { data } = await api<unknown>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
      skipUnauthorizedHandler: true,
    });
    const tokenData = data as { access_token: string };
    setToken(tokenData.access_token);
    resetUnauthorizedFlag();
    setUser({ id: "", username });
  }, []);

  const logout = useCallback(() => {
    removeToken();
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
