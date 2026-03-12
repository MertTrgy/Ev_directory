import { useEffect, useMemo, useState } from 'react';

import { fetchVehicleDetail, fetchVehicles } from './api';
import { VehicleCard } from './components/VehicleCard';
import { VehicleDrawer } from './components/VehicleDrawer';
import type { VehicleDetail, VehicleSummary } from './types';

const PAGE_SIZE = 12;

export default function App() {
  const [vehicles, setVehicles] = useState<VehicleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingList, setLoadingList] = useState(false);
  const [listError, setListError] = useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeSummary, setActiveSummary] = useState<VehicleSummary | null>(null);
  const [activeDetail, setActiveDetail] = useState<VehicleDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailsCache, setDetailsCache] = useState<Record<number, VehicleDetail>>({});

  const hasMore = useMemo(() => vehicles.length < total, [vehicles.length, total]);

  useEffect(() => {
    void loadVehicles(0, true);
  }, []);

  async function loadVehicles(nextOffset: number, replace = false) {
    setLoadingList(true);
    setListError(null);
    try {
      const response = await fetchVehicles(PAGE_SIZE, nextOffset);
      setTotal(response.total);
      setOffset(response.offset + response.items.length);
      setVehicles((previous) => (replace ? response.items : [...previous, ...response.items]));
    } catch (error) {
      setListError(error instanceof Error ? error.message : 'Could not load vehicles');
    } finally {
      setLoadingList(false);
    }
  }

  // We cache details in memory so users can reopen cards instantly.
  async function handleMoreInfo(vehicle: VehicleSummary) {
    setActiveSummary(vehicle);
    setDrawerOpen(true);
    setDetailError(null);

    const cached = detailsCache[vehicle.id];
    if (cached) {
      setActiveDetail(cached);
      return;
    }

    setLoadingDetail(true);
    try {
      const detail = await fetchVehicleDetail(vehicle.id);
      setActiveDetail(detail);
      setDetailsCache((previous) => ({ ...previous, [vehicle.id]: detail }));
    } catch (error) {
      setDetailError(error instanceof Error ? error.message : 'Could not load vehicle detail');
      setActiveDetail(null);
    } finally {
      setLoadingDetail(false);
    }
  }

  function closeDrawer() {
    setDrawerOpen(false);
    setActiveSummary(null);
    setActiveDetail(null);
    setDetailError(null);
  }

  return (
    <div className="page-shell">
      <div className="aurora aurora-left" />
      <div className="aurora aurora-right" />

      <main className="content">
        <header className="hero">
          <p className="eyebrow">OpenEV Data Explorer</p>
          <h1>Browse Electric Vehicles</h1>
          <p>
            Cards show the quick stats. Use <strong>More info</strong> to open a drawer with all available payload
            details.
          </p>
        </header>

        {listError ? <p className="error-text">{listError}</p> : null}

        <section className="vehicle-grid">
          {vehicles.map((vehicle) => (
            <VehicleCard key={vehicle.id} vehicle={vehicle} onMoreInfo={handleMoreInfo} />
          ))}
        </section>

        <div className="actions">
          <button
            type="button"
            className="load-more-button"
            disabled={loadingList || !hasMore}
            onClick={() => void loadVehicles(offset)}
          >
            {loadingList ? 'Loading...' : hasMore ? 'Load more vehicles' : 'No more vehicles'}
          </button>
        </div>
      </main>

      <VehicleDrawer
        open={drawerOpen}
        summary={activeSummary}
        detail={activeDetail}
        loading={loadingDetail}
        error={detailError}
        onClose={closeDrawer}
      />
    </div>
  );
}
