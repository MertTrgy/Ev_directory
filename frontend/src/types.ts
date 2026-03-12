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
