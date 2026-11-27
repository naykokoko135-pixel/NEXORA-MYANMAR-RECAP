// Fetch wrapper: CSRF, error parsing, 401 -> login, 429 -> retry-after.
export class ApiError extends Error {
  constructor(message, status, code, extra = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code || null;
    Object.assign(this, extra);
  }
}

let csrf = null;
let onUnauthorized = () => {};
export const setCsrf = (t) => { csrf = t; };
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

function qs(params) {
  if (!params) return '';
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== '') u.set(k, String(v));
  const s = u.toString();
  return s ? '?' + s : '';
}

async function request(method, path, { params, body, form, noAuthRedirect } = {}) {
  const headers = { Accept: 'application/json' };
  if (method !== 'GET') headers['X-CSRF-Token'] = csrf || '';
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body); }
  let res;
  try {
    res = await fetch(path + qs(params), { method, headers, body: payload, credentials: 'same-origin' });
  } catch (e) {
    throw new ApiError('Network error: backend unreachable', 0, 'network');
  }
  const text = await res.text();
  let data = null;
  if (text) { try { data = JSON.parse(text); } catch { data = null; } }
  if (!res.ok) {
    let msg = (data && data.error) || `Request failed (${res.status})`;
    const extra = {};
    if (res.status === 429) {
      const ra = parseInt(res.headers.get('Retry-After') || '', 10);
      extra.retryAfter = isNaN(ra) ? null : ra;
      msg = `Rate limited. ${ra ? `Retry in ${ra}s.` : 'Please retry shortly.'}`;
    }
    if (res.status === 403 && data?.code === 'read_only') msg = 'Read-only account: this action needs the admin role.';
    const err = new ApiError(msg, res.status, data && data.code, extra);
    if (res.status === 401 && !noAuthRedirect) onUnauthorized(err);
    throw err;
  }
  return data ?? {};
}

export const api = {
  get: (path, params, opts) => request('GET', path, { params, ...opts }),
  post: (path, body = {}, opts) => request('POST', path, { body, ...opts }),
  put: (path, body = {}, opts) => request('PUT', path, { body, ...opts }),
  del: (path, params, opts) => request('DELETE', path, { params, ...opts }),
  upload: (path, formData, opts) => request('POST', path, { form: formData, ...opts }),
};
