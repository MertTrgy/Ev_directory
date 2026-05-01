import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { login as apiLogin, signup as apiSignup } from '../api';
import type { User } from '../types';

type AuthContextValue = {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem('ev_token');
    const storedUser = localStorage.getItem('ev_user');
    if (stored && storedUser) {
      setToken(stored);
      setUser(JSON.parse(storedUser) as User);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const resp = await apiLogin(email, password);
    localStorage.setItem('ev_token', resp.access_token);
    localStorage.setItem('ev_user', JSON.stringify(resp.user));
    setToken(resp.access_token);
    setUser(resp.user);
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const resp = await apiSignup(email, password);
    localStorage.setItem('ev_token', resp.access_token);
    localStorage.setItem('ev_user', JSON.stringify(resp.user));
    setToken(resp.access_token);
    setUser(resp.user);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('ev_token');
    localStorage.removeItem('ev_user');
    setToken(null);
    setUser(null);
  }, []);

  return <AuthContext.Provider value={{ user, token, login, signup, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
