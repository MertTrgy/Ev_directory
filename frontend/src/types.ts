export type VehicleSummary = {
  id: number;
  source_name: string;
  source_vehicle_id: string;
  vehicle_slug: string | null;
  vehicle_name: string | null;
  market: string;
  raw_source_url: string | null;
  image_url: string | null;
  updated_at: string;
  is_favorite: boolean;
  year: number | null;
  brand: string | null;
  range_km: number | null;
  power_kw: number | null;
  battery_kwh: number | null;
};

export type VehicleListResponse = {
  items: VehicleSummary[];
  total: number;
  limit: number;
  offset: number;
};

export type VehicleDetail = VehicleSummary & {
  payload: Record<string, unknown>;
};

export type User = {
  id: number;
  email: string;
  role: string;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};

export type SearchFilters = {
  search: string;
  brand: string;
  market: string;
  year_min: string;
  year_max: string;
  range_min_km: string;
  range_max_km: string;
  body_style: string;
  drivetrain: string;
  sort_by: string;
  order: string;
};

export const DEFAULT_FILTERS: SearchFilters = {
  search: '',
  brand: '',
  market: '',
  year_min: '',
  year_max: '',
  range_min_km: '',
  range_max_km: '',
  body_style: '',
  drivetrain: '',
  sort_by: 'updated',
  order: 'desc',
};
