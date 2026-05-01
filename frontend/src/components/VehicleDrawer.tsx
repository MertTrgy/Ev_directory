import { useEffect } from 'react';
import type { VehicleDetail, VehicleSummary } from '../types';

type Props = {
  open: boolean;
  summary: VehicleSummary | null;
  detail: VehicleDetail | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onToggleFavorite?: () => void;
  isLoggedIn?: boolean;
};

const PLACEHOLDER = '/car-placeholder.svg';

function drawerTitle(summary: VehicleSummary | null, detail: VehicleDetail | null): string {
  return detail?.vehicle_name ?? summary?.vehicle_name ?? 'Vehicle details';
}

type Payload = Record<string, unknown>;

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="spec-section">
      <h4 className="spec-section-title">{title}</h4>
      {children}
    </div>
  );
}

function SpecRow({ label, value, unit }: { label: string; value: unknown; unit?: string }) {
  if (value === null || value === undefined || value === '') return null;
  return (
    <div className="spec-row">
      <span className="spec-row-label">{label}</span>
      <span className="spec-row-value">{String(value)}{unit ? ` ${unit}` : ''}</span>
    </div>
  );
}

function StructuredPayload({ payload }: { payload: Payload }) {
  const p = payload as Record<string, unknown>;

  return (
    <div className="structured-specs">
      <Section title="Overview">
        <SpecRow label="Brand" value={p.brand as string} />
        <SpecRow label="Model" value={p.model as string} />
        <SpecRow label="Trim" value={p.trim as string} />
        <SpecRow label="Year" value={p.year as number} />
        <SpecRow label="Body style" value={p.bodyStyle as string} />
        <SpecRow label="Seats" value={p.seats as number} />
        <SpecRow label="Status" value={p.availabilityStatus as string} />
      </Section>

      <Section title="Performance">
        <SpecRow label="Power" value={p.powerKw as number} unit="kW" />
        <SpecRow label="Drivetrain" value={(p.drivetrain as string)?.toUpperCase()} />
        <SpecRow label="0–100 km/h" value={p.acceleration as number} unit="s" />
        <SpecRow label="Top speed" value={p.topSpeedKmh as number} unit="km/h" />
      </Section>

      <Section title="Range & Battery">
        <SpecRow label="Range (WLTP)" value={p.rangeKm as number} unit="km" />
        <SpecRow label="Battery" value={p.batteryKwh as number} unit="kWh" />
      </Section>

      <Section title="Charging">
        <SpecRow label="AC charge" value={p.acChargeKw as number} unit="kW" />
        <SpecRow label="DC charge" value={p.dcChargeKw as number} unit="kW" />
      </Section>

      {p.sourceLinks && Array.isArray(p.sourceLinks) && (p.sourceLinks as string[]).length > 0 ? (
        <Section title="Sources">
          {(p.sourceLinks as string[]).map((url, i) => (
            <a key={i} href={url} target="_blank" rel="noopener noreferrer" className="source-link">
              {url}
            </a>
          ))}
        </Section>
      ) : null}
    </div>
  );
}

export function VehicleDrawer({ open, summary, detail, loading, error, onClose, onToggleFavorite, isLoggedIn }: Props) {
  useEffect(() => {
    if (!open) return;
    const onEscape = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onEscape);
    return () => window.removeEventListener('keydown', onEscape);
  }, [open, onClose]);

  if (!open) return null;

  const heroImage = detail?.image_url ?? summary?.image_url ?? PLACEHOLDER;
  const payload = detail?.payload ?? null;

  return (
    <div className="drawer-backdrop" onClick={onClose} role="presentation">
      <aside
        className="drawer-panel"
        role="dialog"
        aria-modal="true"
        aria-label="Vehicle details"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer-header">
          <h2>{drawerTitle(summary, detail)}</h2>
          <div className="drawer-header-actions">
            {isLoggedIn && detail ? (
              <button
                type="button"
                className={`fav-btn-lg ${detail.is_favorite ? 'fav-active' : ''}`}
                onClick={onToggleFavorite}
                title={detail.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
              >
                {detail.is_favorite ? '♥ Saved' : '♡ Save'}
              </button>
            ) : null}
            <button type="button" className="drawer-close-button" onClick={onClose}>✕</button>
          </div>
        </header>

        <img
          className="drawer-image"
          src={heroImage}
          alt={drawerTitle(summary, detail)}
          onError={(e) => { e.currentTarget.src = PLACEHOLDER; }}
        />

        {loading ? <p style={{ padding: '1.5rem' }}>Loading vehicle details…</p> : null}
        {error ? <p className="error-text" style={{ padding: '1rem' }}>{error}</p> : null}

        {!loading && detail && payload ? (
          <section className="drawer-metadata">
            <div className="drawer-meta-row">
              <span><strong>Market:</strong> {detail.market}</span>
              <span><strong>Source:</strong> {detail.source_name}</span>
            </div>
            <StructuredPayload payload={payload as Payload} />
          </section>
        ) : null}
      </aside>
    </div>
  );
}
