"use client";

// Keeps track of who is logged in and shares it with every component.
//
//   const { user, login, logout } = useAuth();
//
// `user` is:
//   undefined  while we're still asking the API (show a loader)
//   null       when nobody is logged in
//   a User     when someone is logged in

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { User } from "@/lib/types";

interface AuthContextValue {
  user: User | null | undefined;
  login: (email: string, password: string) => Promise<User>;
  /** Ends the session and sends the browser to /login. */
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  const refresh = useCallback(async () => {
    try {
      setUser(await api.get<User>("/auth/me"));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setUser(null);
      } else {
        throw err;
      }
    }
  }, []);

  useEffect(() => {
    // Ask the API once, on first load, whether we already have a session.
    api
      .get<User>("/auth/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const loggedIn = await api.post<User>("/auth/login", { email, password });
    setUser(loggedIn);
    return loggedIn;
  }, []);

  const logout = useCallback(async () => {
    await api.post("/auth/logout");
    // A full page load (rather than client-side navigation) wipes any data
    // the previous user had loaded in memory.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination -- intentional full reload
    window.location.assign("/login");
  }, []);

  const value = useMemo(() => ({ user, login, logout, refresh }), [user, login, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
