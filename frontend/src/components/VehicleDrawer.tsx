import { useEffect } from 'react';

import type { VehicleDetail, VehicleSummary } from '../types';

type VehicleDrawerProps = {
  open: boolean;
  summary: VehicleSummary | null;
  detail: VehicleDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
};

const PLACEHOLDER_IMAGE = '/car-placeholder.svg';

function drawerTitle(summary: VehicleSummary | null, detail: VehicleDetail | null): string {
  return detail?.vehicle_name ?? summary?.vehicle_name ?? 'Vehicle details';
}

export function VehicleDrawer({ open, summary, detail, loading, error, onClose }: VehicleDrawerProps) {
  // Keyboard close keeps the drawer usable even without a mouse.
  useEffect(() => {
    if (!open) {
      return;
    }

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };

    window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const heroImage = detail?.image_url ?? summary?.image_url ?? PLACEHOLDER_IMAGE;
  const payload = detail?.payload ?? null;

  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside
        className="drawer-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Vehicle details"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="drawer-header">
          <h2>{drawerTitle(summary, detail)}</h2>
          <button type="button" className="drawer-close-button" onClick={onClose}>
            Close
          </button>
        </header>

        <img
          className="drawer-image"
          src={heroImage}
          alt={drawerTitle(summary, detail)}
          onError={(event) => {
            event.currentTarget.src = PLACEHOLDER_IMAGE;
          }}
        />

        {loading ? <p>Loading vehicle details...</p> : null}
        {error ? <p className="error-text">{error}</p> : null}

        {!loading && detail ? (
          <section className="drawer-metadata">
            <p>
              <strong>Source:</strong> {detail.source_name}
            </p>
            <p>
              <strong>Vehicle ID:</strong> {detail.source_vehicle_id}
            </p>
            <p>
              <strong>Market:</strong> {detail.market}
            </p>
            <p>
              <strong>Slug:</strong> {detail.vehicle_slug ?? 'n/a'}
            </p>
            <p>
              <strong>Raw URL:</strong> {detail.raw_source_url ?? 'n/a'}
            </p>

            <h3>Full payload</h3>
            <pre className="payload-preview">{JSON.stringify(payload, null, 2)}</pre>
          </section>
        ) : null}
      </aside>
    </div>
  );
}
