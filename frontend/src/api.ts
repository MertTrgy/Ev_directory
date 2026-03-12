import type { VehicleDetail, VehicleListResponse } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// Centralized fetch helper keeps request/response handling consistent.
async function requestJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return (await response.json()) as T;
}

export async function fetchVehicles(limit: number, offset: number): Promise<VehicleListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return requestJson<VehicleListResponse>(`/vehicles?${params.toString()}`);
}

export async function fetchVehicleDetail(vehicleId: number): Promise<VehicleDetail> {
  return requestJson<VehicleDetail>(`/vehicles/${vehicleId}`);
}
