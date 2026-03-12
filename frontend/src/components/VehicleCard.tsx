import type { VehicleSummary } from '../types';

type VehicleCardProps = {
  vehicle: VehicleSummary;
  onMoreInfo: (vehicle: VehicleSummary) => void;
};

const PLACEHOLDER_IMAGE = '/car-placeholder.svg';

function formatTimestamp(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function VehicleCard({ vehicle, onMoreInfo }: VehicleCardProps) {
  return (
    <article className="vehicle-card">
      <img
        className="vehicle-card-image"
        src={vehicle.image_url ?? PLACEHOLDER_IMAGE}
        alt={vehicle.vehicle_name ?? vehicle.source_vehicle_id}
        onError={(event) => {
          event.currentTarget.src = PLACEHOLDER_IMAGE;
        }}
      />

      <div className="vehicle-card-content">
        <h3>{vehicle.vehicle_name ?? 'Unnamed Vehicle'}</h3>
        <p className="vehicle-subtitle">{vehicle.source_vehicle_id}</p>

        <div className="vehicle-stats">
          <span>Market: {vehicle.market}</span>
          <span>Updated: {formatTimestamp(vehicle.updated_at)}</span>
        </div>

        <button className="vehicle-more-button" onClick={() => onMoreInfo(vehicle)} type="button">
          More info
        </button>
      </div>
    </article>
  );
}
