// JSON client for the console server, with a connection indicator.

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

function setConnection(ok) {
  const conn = document.getElementById('conn');
  if (!conn) return;
  const state = ok ? 'ok' : 'lost';
  if (conn.dataset.state === state) return;
  conn.dataset.state = state;
  conn.querySelector('.conn-label').textContent = ok ? 'Connected' : 'Server unreachable';
}

/** Call the API. Throws ApiError (status 0 = the server could not be reached). */
export async function api(path, { method = 'GET', body } = {}) {
  const init = { method, headers: { Accept: 'application/json' } };
  if (body !== undefined || (method !== 'GET' && method !== 'DELETE')) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body ?? {});
  }
  let response;
  try {
    response = await fetch(path, init);
  } catch {
    setConnection(false);
    throw new ApiError('Cannot reach the console server. Is `python -m ui` still running?', 0);
  }
  setConnection(true);
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch {
    /* non-JSON body */
  }
  if (!response.ok) {
    throw new ApiError((data && data.error) || `${response.status} ${response.statusText}`, response.status);
  }
  return data;
}
