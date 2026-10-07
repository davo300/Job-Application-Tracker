export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function csrfToken(): string | undefined {
  for (const name of ['__Host-tracker_csrf', 'tracker_csrf']) {
    const cookie = document.cookie.split('; ').find((item) => item.startsWith(`${name}=`));
    if (cookie) return decodeURIComponent(cookie.slice(name.length + 1));
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set('X-Requested-With', 'job-tracker');
  if (options.body) headers.set('Content-Type', 'application/json');
  if (options.method && !['GET', 'HEAD', 'OPTIONS'].includes(options.method)) {
    const csrf = csrfToken();
    if (csrf) headers.set('X-CSRF-Token', csrf);
  }
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: 'same-origin',
  });
  if (!response.ok) {
    if (response.status === 401 && !['/auth/login', '/auth/register'].includes(path))
      window.dispatchEvent(new Event('session-expired'));
    const data = await response.json().catch(() => ({}));
    const message =
      typeof data.detail === 'string'
        ? data.detail
        : response.status === 422
          ? path.startsWith('/auth/')
            ? 'Check your email and password. New passwords must be 12–128 characters.'
            : 'Check the form fields, dates, URLs, and salary values.'
          : 'The server could not complete your request. Please try again.';
    throw new ApiError(response.status, message);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
