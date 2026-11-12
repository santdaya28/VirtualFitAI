import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import {
  getAuthToken,
  clearAuthToken,
  loginUser as apiLogin,
  registerUser as apiRegister,
  fetchCurrentUser,
  logoutUser as apiLogout,
} from '../services/api';

const AuthContext = createContext({
  user: null,
  token: null,
  role: 'guest',
  isAuthenticated: false,
  isCustomer: false,
  isShopOwner: false,
  isAdmin: false,
  isLoading: true,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(getAuthToken());
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const currentToken = getAuthToken();
    if (!currentToken) {
      setUser(null);
      setToken(null);
      setIsLoading(false);
      return null;
    }

    try {
      const profile = await fetchCurrentUser();
      if (profile) {
        setUser(profile);
        setToken(currentToken);
        return profile;
      } else {
        clearAuthToken();
        setUser(null);
        setToken(null);
        return null;
      }
    } catch {
      clearAuthToken();
      setUser(null);
      setToken(null);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async ({ email, password }) => {
    const res = await apiLogin({ email, password });
    setToken(res.access_token);
    setUser(res.user);
    return res;
  };

  const register = async ({ email, password, fullName, role, shopName }) => {
    const res = await apiRegister({ email, password, fullName, role, shopName });
    setToken(res.access_token);
    setUser(res.user);
    return res;
  };

  const logout = async () => {
    try {
      await apiLogout();
    } catch {
      clearAuthToken();
    } finally {
      setUser(null);
      setToken(null);
    }
  };

  const role = user?.role || 'guest';
  const isAuthenticated = Boolean(user && token);
  const isCustomer = role === 'customer';
  const isShopOwner = role === 'shop_owner';
  const isAdmin = role === 'admin';

  const value = {
    user,
    token,
    role,
    isAuthenticated,
    isCustomer,
    isShopOwner,
    isAdmin,
    isLoading,
    login,
    register,
    logout,
    refreshUser,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

export default AuthContext;

