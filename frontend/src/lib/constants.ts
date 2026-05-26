/**
 * Application constants.
 */

export const APP_NAME = "ai_agent";
export const APP_DESCRIPTION = "My FastAPI project";

// API Routes (direct to backend via CloudFront /api/v1/*)
export const API_ROUTES = {
  // Auth
  LOGIN: "/auth/login",
  REGISTER: "/auth/register",
  LOGOUT: "/auth/logout",
  REFRESH: "/auth/refresh",
  ME: "/auth/me",

  // Health
  HEALTH: "/health",

  // Users
  USERS: "/users",

  // Chat (AI Agent)
  CHAT: "/chat",
} as const;

// Navigation routes
export const ROUTES = {
  HOME: "/",
  LOGIN: "/login",
  REGISTER: "/register",
  DASHBOARD: "/dashboard",
  CHAT: "/chat",
  PROFILE: "/profile",
  SETTINGS: "/settings",
  DOCUMENTS: "/documents",
  RAG: "/rag",
  ADMIN_RATINGS: "/admin/ratings",
  ADMIN_CONVERSATIONS: "/admin/conversations",
  HEALTH_CHECK: "/health-check",
} as const;

// Backend URL (for direct links like API docs)
export const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:8000";
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}`;
}
