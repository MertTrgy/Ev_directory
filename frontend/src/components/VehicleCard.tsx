import type { VehicleSummary } from '../types';

type Props = {
  vehicle: VehicleSummary;
  onMoreInfo: (vehicle: VehicleSummary) => void;
  onToggleFavorite?: (vehicle: VehicleSummary) => void;
  onToggleCompare?: (vehicle: VehicleSummary) => void;
  isInCompare?: boolean;
  isLoggedIn?: boolean;
};

const PLACEHOLDER = '/car-placeholder.svg';

export function VehicleCard({ vehicle, onMoreInfo, onToggleFavorite, onToggleCompare, isInCompare, isLoggedIn }: Props) {
  return (
    <article className="vehicle-card">
      <div className="card-image-wrap">
        <img
          className="vehicle-card-image"
          src={vehicle.image_url ?? PLACEHOLDER}
          alt={vehicle.vehicle_name ?? vehicle.source_vehicle_id}
          onError={(e) => { e.currentTarget.src = PLACEHOLDER; }}
        />
        {isLoggedIn ? (
          <button
            type="button"
            className={`fav-btn ${vehicle.is_favorite ? 'fav-active' : ''}`}
            title={vehicle.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
            onClick={() => onToggleFavorite?.(vehicle)}
          >
            {vehicle.is_favorite ? '♥' : '♡'}
          </button>
        ) : null}
      </div>

      <div className="vehicle-card-content">
        <h3>{vehicle.vehicle_name ?? 'Unnamed Vehicle'}</h3>
        {vehicle.brand ? <p className="vehicle-subtitle">{vehicle.brand}{vehicle.year ? ` · ${vehicle.year}` : ''}</p> : null}

        <div className="vehicle-quick-specs">
          {vehicle.range_km != null ? <span className="spec-badge">⚡ {vehicle.range_km} km</span> : null}
          {vehicle.power_kw != null ? <span className="spec-badge">🔋 {vehicle.battery_kwh} kWh</span> : null}
          {vehicle.power_kw != null ? <span className="spec-badge">⚙ {vehicle.power_kw} kW</span> : null}
        </div>

        <div className="vehicle-stats">
          <span>{vehicle.market}</span>
        </div>

        <div className="card-actions">
          <button className="vehicle-more-button" onClick={() => onMoreInfo(vehicle)} type="button">
            More info
          </button>
          <button
            type="button"
            className={`compare-btn ${isInCompare ? 'compare-active' : ''}`}
            onClick={() => onToggleCompare?.(vehicle)}
            title={isInCompare ? 'Remove from comparison' : 'Add to comparison'}
          >
            {isInCompare ? '✓ Comparing' : '+ Compare'}
          </button>
        </div>
      </div>
    </article>
  );
}
