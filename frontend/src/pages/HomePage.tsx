import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import { addFavorite, fetchVehicleDetail, fetchVehicles, removeFavorite } from '../api';
import { ComparisonView } from '../components/ComparisonView';
import { EmptyState } from '../components/EmptyState';
import { SearchFilter } from '../components/SearchFilter';
import { SkeletonCard } from '../components/SkeletonCard';
import { StatsBar } from '../components/StatsBar';
import { VehicleCard } from '../components/VehicleCard';
import { VehicleDrawer } from '../components/VehicleDrawer';
import { useAuth } from '../context/AuthContext';
import { DEFAULT_FILTERS, type SearchFilters, type VehicleDetail, type VehicleSummary } from '../types';

const PAGE_SIZE = 12;

type Props = { onShowAuth: () => void };

export function HomePage({ onShowAuth }: Props) {
  const { user } = useAuth();
  const [vehicles, setVehicles] = useState<VehicleSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loadingList, setLoadingList] = useState(true);
  const [listError, setListError] = useState<string | null>(null);

  const [filters, setFilters] = useState<SearchFilters>(DEFAULT_FILTERS);
  const filtersRef = useRef(filters);
  filtersRef.current = filters;

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeSummary, setActiveSummary] = useState<VehicleSummary | null>(null);
  const [activeDetail, setActiveDetail] = useState<VehicleDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailsCache, setDetailsCache] = useState<Record<number, VehicleDetail>>({});

  const [compareIds, setCompareIds] = useState<number[]>([]);
  const [showCompare, setShowCompare] = useState(false);

  const hasMore = useMemo(() => vehicles.length < total, [vehicles.length, total]);

  async function loadVehicles(nextOffset: number, replace = false, overrideFilters?: SearchFilters) {
    setLoadingList(true);
    setListError(null);
    const activeFilters = overrideFilters ?? filtersRef.current;
    try {
      const response = await fetchVehicles(PAGE_SIZE, nextOffset, activeFilters);
      setTotal(response.total);
      setOffset(response.offset + response.items.length);
      setVehicles((prev) => (replace ? response.items : [...prev, ...response.items]));
    } catch (err) {
      setListError(err instanceof Error ? err.message : 'Could not load vehicles');
    } finally {
      setLoadingList(false);
    }
  }

  useEffect(() => {
    void loadVehicles(0, true);
  }, []);

  function handleFiltersChange(newFilters: SearchFilters) {
    setFilters(newFilters);
    setOffset(0);
    void loadVehicles(0, true, newFilters);
  }

  function handleFiltersReset() {
    setFilters(DEFAULT_FILTERS);
    setOffset(0);
    void loadVehicles(0, true, DEFAULT_FILTERS);
  }

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
      setDetailsCache((prev) => ({ ...prev, [vehicle.id]: detail }));
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Could not load vehicle detail');
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

  const handleToggleFavorite = useCallback(async (vehicle: VehicleSummary) => {
    if (!user) { onShowAuth(); return; }
    try {
      if (vehicle.is_favorite) {
        await removeFavorite(vehicle.id);
        toast.success('Removed from favorites');
      } else {
        await addFavorite(vehicle.id);
        toast.success('Added to favorites');
      }
      setVehicles((prev) =>
        prev.map((v) => (v.id === vehicle.id ? { ...v, is_favorite: !v.is_favorite } : v)),
      );
      setDetailsCache((prev) => {
        const cached = prev[vehicle.id];
        if (!cached) return prev;
        return { ...prev, [vehicle.id]: { ...cached, is_favorite: !cached.is_favorite } };
      });
      setActiveDetail((prev) =>
        prev?.id === vehicle.id ? { ...prev, is_favorite: !prev.is_favorite } : prev,
      );
    } catch {
      toast.error('Could not update favorites');
    }
  }, [user, onShowAuth]);

  function handleToggleCompare(vehicle: VehicleSummary) {
    setCompareIds((prev) => {
      if (prev.includes(vehicle.id)) return prev.filter((id) => id !== vehicle.id);
      if (prev.length >= 4) { toast.error('You can compare up to 4 vehicles'); return prev; }
      return [...prev, vehicle.id];
    });
  }

  const skeletonCount = PAGE_SIZE;

  return (
    <>
      <StatsBar />

      <SearchFilter filters={filters} onChange={handleFiltersChange} onReset={handleFiltersReset} />

      {listError ? <p className="error-text">{listError}</p> : null}

      {!loadingList && !listError && (
        <p className="result-count">{total} vehicle{total !== 1 ? 's' : ''}</p>
      )}

      <section className="vehicle-grid">
        {loadingList && vehicles.length === 0
          ? Array.from({ length: skeletonCount }, (_, i) => <SkeletonCard key={i} />)
          : vehicles.map((vehicle) => (
              <VehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                onMoreInfo={handleMoreInfo}
                onToggleFavorite={handleToggleFavorite}
                onToggleCompare={handleToggleCompare}
                isInCompare={compareIds.includes(vehicle.id)}
                isLoggedIn={!!user}
              />
            ))}
      </section>

      {!loadingList && vehicles.length === 0 && !listError ? (
        <EmptyState onReset={handleFiltersReset} />
      ) : null}

      <div className="actions">
        <button
          type="button"
          className="load-more-button"
          disabled={loadingList || !hasMore}
          onClick={() => void loadVehicles(offset)}
        >
          {loadingList && vehicles.length > 0 ? 'Loading…' : hasMore ? 'Load more' : 'No more vehicles'}
        </button>
      </div>

      {compareIds.length >= 1 ? (
        <div className="compare-bar">
          <span>{compareIds.length} vehicle{compareIds.length > 1 ? 's' : ''} selected</span>
          <button
            type="button"
            className="btn-primary"
            disabled={compareIds.length < 2}
            onClick={() => setShowCompare(true)}
          >
            Compare {compareIds.length < 2 ? '(need 2+)' : ''}
          </button>
          <button type="button" className="btn-ghost" onClick={() => setCompareIds([])}>Clear</button>
        </div>
      ) : null}

      <VehicleDrawer
        open={drawerOpen}
        summary={activeSummary}
        detail={activeDetail}
        loading={loadingDetail}
        error={detailError}
        onClose={closeDrawer}
        onToggleFavorite={activeSummary ? () => void handleToggleFavorite(activeSummary) : undefined}
        isLoggedIn={!!user}
      />

      {showCompare ? <ComparisonView ids={compareIds} onClose={() => setShowCompare(false)} /> : null}
    </>
  );
}
