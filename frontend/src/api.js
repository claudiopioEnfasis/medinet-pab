const PREFIX = '/api';
// Token de corta duración en memoria: no persiste en localStorage/sessionStorage.
let accessToken = null;
let onUnauthorized = null;
export function setToken(value) { accessToken = value; }
export function setUnauthorizedHandler(handler) { onUnauthorized = handler; }

export function errorMessage(detail) {
  if (Array.isArray(detail)) {
    return detail.map(item => typeof item === 'string' ? item : (item.msg || 'Error de validación')).join(' · ');
  }
  if (typeof detail === 'string') return detail;
  return 'No se pudo completar la solicitud.';
}

export async function request(path, { method = 'GET', body, signal } = {}) {
  let response;
  try {
    response = await fetch(`${PREFIX}${path}`, {
      method,
      headers: {
        ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
      cache: 'no-store',
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('No hay conexión con la API. Comprueba que Docker esté ejecutándose.');
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && path !== '/auth/login') {
      accessToken = null;
      onUnauthorized?.();
      throw new Error('Tu sesión expiró. Inicia sesión nuevamente.');
    }
    throw new Error(errorMessage(data?.detail) || `Error HTTP ${response.status}`);
  }
  return data;
}

export function checkAvailability({ room_id, patient_id, staff_ids, starts_at, ends_at }) {
  const query = new URLSearchParams({ room_id: String(room_id), patient_id: String(patient_id), starts_at, ends_at });
  staff_ids.forEach(id => query.append('staff_ids', String(id)));
  return request(`/availability?${query.toString()}`);
}

export const API = {
  login: body => request('/auth/login', { method: 'POST', body }),
  me: () => request('/auth/me'),
  rooms: () => request('/operating-rooms'),
  patients: () => request('/patients'),
  staff: () => request('/medical-staff'),
  surgeries: () => request('/surgeries'),
  createRoom: body => request('/operating-rooms', { method: 'POST', body }),
  roomStatus: (id, status) => request(`/operating-rooms/${id}/status`, { method: 'PATCH', body: { status } }),
  createPatient: body => request('/patients', { method: 'POST', body }),
  createStaff: body => request('/medical-staff', { method: 'POST', body }),
  createSurgery: body => request('/surgeries', { method: 'POST', body }),
  surgeryStatus: (id, status) => request(`/surgeries/${id}/status`, { method: 'PATCH', body: { status } }),
};
