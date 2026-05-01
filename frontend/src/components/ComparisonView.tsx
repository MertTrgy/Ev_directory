import { useEffect, useState } from 'react';
import { fetchCompare } from '../api';
import type { VehicleDetail } from '../types';

type Props = {
  ids: number[];
  onClose: () => void;
};

const SPEC_ROWS: { label: string; key: string; unit?: string }[] = [
  { label: 'Year', key: 'year' },
  { label: 'Body style', key: 'bodyStyle' },
  { label: 'Drivetrain', key: 'drivetrain' },
  { label: 'Range', key: 'rangeKm', unit: 'km' },
  { label: 'Power', key: 'powerKw', unit: 'kW' },
  { label: 'Battery', key: 'batteryKwh', unit: 'kWh' },
  { label: 'AC charge', key: 'acChargeKw', unit: 'kW' },
  { label: 'DC charge', key: 'dcChargeKw', unit: 'kW' },
  { label: '0–100 km/h', key: 'acceleration', unit: 's' },
  { label: 'Top speed', key: 'topSpeedKmh', unit: 'km/h' },
  { label: 'Seats', key: 'seats' },
];

const PLACEHOLDER = '/car-placeholder.svg';

function val(vehicle: VehicleDetail, key: string): string {
  const p = vehicle.payload as Record<string, unknown>;
  const v = p[key];
  return v !== null && v !== undefined ? String(v) : '—';
}

export function ComparisonView({ ids, onClose }: Props) {
  const [vehicles, setVehicles] = useState<VehicleDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ids.length < 2) return;
    setLoading(true);
    fetchCompare(ids)
      .then((r) => setVehicles(r.items))
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false));
  }, [ids]);

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="comparison-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header className="modal-header">
          <h2>Compare vehicles</h2>
          <button type="button" className="drawer-close-button" onClick={onClose}>✕</button>
        </header>

        {loading ? <p style={{ padding: '2rem' }}>Loading…</p> : null}
        {error ? <p className="error-text" style={{ padding: '1rem' }}>{error}</p> : null}

        {!loading && vehicles.length > 0 ? (
          <div className="comparison-body">
            <table className="comparison-table">
              <thead>
                <tr>
                  <th className="spec-col">Spec</th>
                  {vehicles.map((v) => (
                    <th key={v.id} className="vehicle-col">
                      <img
                        src={v.image_url ?? PLACEHOLDER}
                        alt={v.vehicle_name ?? ''}
                        className="compare-thumb"
                        onError={(e) => { e.currentTarget.src = PLACEHOLDER; }}
                      />
                      <span>{v.vehicle_name ?? v.source_vehicle_id}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {SPEC_ROWS.map((row) => (
                  <tr key={row.key}>
                    <td className="spec-label">{row.label}</td>
                    {vehicles.map((v) => (
                      <td key={v.id} className="spec-value">
                        {val(v, row.key)}{val(v, row.key) !== '—' && row.unit ? ` ${row.unit}` : ''}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}
      </div>
    </div>
  );
}
