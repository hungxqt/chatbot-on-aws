/**
 * Client-side API client.
 * Requests go directly to /api/v1/* which CloudFront routes to the backend ALB.
 * Authentication is handled via httpOnly cookies set by the backend.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public message: string,
    public data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  params?: Record<string, string>;
  body?: unknown;
}

class ApiClient {
  private async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { params, body, ...fetchOptions } = options;

    let url = `/api/v1${endpoint}`;

    if (params) {
      const searchParams = new URLSearchParams(params);
      url += `?${searchParams.toString()}`;
    }

    const headers: Record<string, string> = {
      ...((fetchOptions.headers as Record<string, string>) || {}),
    };

    if (body && !(body instanceof FormData)) {
      headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
      ...fetchOptions,
      headers,
      credentials: "include",
      body: body instanceof FormData ? (body as BodyInit) : body ? JSON.stringify(body) : undefined,
    });

    if (!response.ok) {
      let errorData;
      try {
        errorData = await response.json();
      } catch {
        errorData = null;
      }
      throw new ApiError(
        response.status,
        errorData?.error?.message || errorData?.detail || errorData?.message || "Request failed",
        errorData,
      );
    }

    const text = await response.text();
    if (!text) {
      return null as T;
    }

    return JSON.parse(text);
  }

  get<T>(endpoint: string, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: "GET" });
  }

  post<T>(endpoint: string, body?: unknown, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: "POST", body });
  }

  put<T>(endpoint: string, body?: unknown, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: "PUT", body });
  }

  patch<T>(endpoint: string, body?: unknown, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: "PATCH", body });
  }

  delete<T>(endpoint: string, options?: RequestOptions) {
    return this.request<T>(endpoint, { ...options, method: "DELETE" });
  }
}

export const apiClient = new ApiClient();
