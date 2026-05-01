import type { SearchFilters, TokenResponse, VehicleDetail, VehicleListResponse } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

function getToken(): string | null {
  return localStorage.getItem('ev_token');
}

async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options?.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `Request failed (${response.status})`);
  }
  return (await response.json()) as T;
}

// ── Vehicles ──────────────────────────────────────────────────────────────────

export async function fetchVehicles(limit: number, offset: number, filters?: Partial<SearchFilters>): Promise<VehicleListResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters) {
    for (const [key, value] of Object.entries(filters)) {
      if (value) params.set(key, String(value));
    }
  }
  return requestJson<VehicleListResponse>(`/vehicles?${params.toString()}`);
}

export async function fetchVehicleDetail(vehicleId: number): Promise<VehicleDetail> {
  return requestJson<VehicleDetail>(`/vehicles/${vehicleId}`);
}

export async function fetchCompare(ids: number[]): Promise<{ items: VehicleDetail[] }> {
  return requestJson(`/vehicles/compare?ids=${ids.join(',')}`);
}

export async function fetchFavorites(): Promise<VehicleListResponse> {
  return requestJson<VehicleListResponse>('/favorites');
}

export async function addFavorite(vehicleId: number): Promise<void> {
  await requestJson(`/favorites/${vehicleId}`, { method: 'POST', body: '' });
}

export async function removeFavorite(vehicleId: number): Promise<void> {
  await requestJson(`/favorites/${vehicleId}`, { method: 'DELETE' });
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function login(email: string, password: string): Promise<TokenResponse> {
  return requestJson<TokenResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function signup(email: string, password: string): Promise<TokenResponse> {
  return requestJson<TokenResponse>('/auth/signup', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

// ── Admin ─────────────────────────────────────────────────────────────────────

export async function triggerSync(): Promise<unknown> {
  return requestJson('/vehicles/json/sync-to-db', { method: 'POST', body: '' });
}

export async function triggerEnrichAll(): Promise<unknown> {
  return requestJson('/vehicles/enrich-all', { method: 'POST', body: '' });
}

export async function fetchEnrichStatus(): Promise<unknown> {
  return requestJson('/vehicles/enrich-status');
}

export async function fetchHealth(): Promise<unknown> {
  return requestJson('/health');
}
