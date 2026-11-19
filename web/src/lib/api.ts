// A tiny wrapper around fetch() for talking to the API.
//
//   const users = await api.get<User[]>("/users");
//   await api.post("/auth/login", { email, password });
//
// Paths are relative to /api. Requests go to the same origin as the web app;
// Next.js forwards them to the API container (see next.config.ts). The session
// cookie is sent automatically by the browser.

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
    credentials: "same-origin",
  });

  if (!res.ok) {
    throw new ApiError(res.status, await errorMessage(res));
  }
  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}

// FastAPI errors look like {"detail": "message"} or, for validation errors,
// {"detail": [{"msg": "...", "loc": [...]}, ...]}. Turn either into a string.
async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json();
    if (typeof data.detail === "string") return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail.map((d: { msg: string }) => d.msg).join("; ");
    }
  } catch {
    // Response wasn't JSON; fall through.
  }
  return `Request failed (${res.status})`;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  put: <T>(path: string, body: unknown) => request<T>("PUT", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
