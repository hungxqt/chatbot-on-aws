"use client";

import { useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { useAuthStore } from "@/stores";
import { apiClient, ApiError } from "@/lib/api-client";
import type { User, LoginRequest, RegisterRequest } from "@/types";
import { ROUTES } from "@/lib/constants";

export function useAuth() {
  const router = useRouter();
  const { user, isAuthenticated, isLoading, setUser, setLoading, logout } = useAuthStore();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const data = await apiClient.get<User>("/auth/me");
        setUser(data);
      } catch {
        setUser(null);
        useAuthStore.getState().setAccessToken(null);
      }
    };

    checkAuth();
  }, [setUser]);

  const login = useCallback(
    async (credentials: LoginRequest) => {
      setLoading(true);
      try {
        const formData = new URLSearchParams();
        formData.append("username", credentials.email);
        formData.append("password", credentials.password);

        const response = await fetch("/api/v1/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded" },
          credentials: "include",
          body: formData.toString(),
        });

        if (!response.ok) {
          const error = await response.json().catch(() => ({ detail: "Login failed" }));
          throw new ApiError(
            response.status,
            error?.error?.message || error?.detail || "Login failed",
            error,
          );
        }

        const data = await response.json();
        useAuthStore.getState().setAccessToken(data.access_token);

        const userData = await apiClient.get<User>("/auth/me");
        setUser(userData);
        router.push(userData.role === "admin" ? ROUTES.DASHBOARD : ROUTES.CHAT);
        return { user: userData, access_token: data.access_token, message: "Login successful" };
      } catch (error) {
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [router, setUser, setLoading],
  );

  const register = useCallback(async (data: RegisterRequest) => {
    const response = await apiClient.post<{ id: string; email: string }>("/auth/register", data);
    return response;
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Ignore logout errors
    } finally {
      logout();
      toast.success("Logged out");
      router.push(ROUTES.LOGIN);
    }
  }, [logout, router]);

  const refreshToken = useCallback(async () => {
    try {
      const refreshResponse = await apiClient.post<{ access_token: string }>("/auth/refresh");
      useAuthStore.getState().setAccessToken(refreshResponse.access_token);
      const userData = await apiClient.get<User>("/auth/me");
      setUser(userData);
      return true;
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        logout();
        router.push(ROUTES.LOGIN);
      }
      return false;
    }
  }, [logout, router, setUser]);

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout: handleLogout,
    refreshToken,
  };
}
