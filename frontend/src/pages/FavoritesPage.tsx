import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';

import { addFavorite, fetchFavorites, fetchVehicleDetail, removeFavorite } from '../api';
import { EmptyState } from '../components/EmptyState';
import { SkeletonCard } from '../components/SkeletonCard';
import { VehicleCard } from '../components/VehicleCard';
import { VehicleDrawer } from '../components/VehicleDrawer';
import { useAuth } from '../context/AuthContext';
import type { VehicleDetail, VehicleSummary } from '../types';

type Props = { onShowAuth: () => void };

export function FavoritesPage({ onShowAuth }: Props) {
  const { user } = useAuth();
  const [favorites, setFavorites] = useState<VehicleSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [activeSummary, setActiveSummary] = useState<VehicleSummary | null>(null);
  const [activeDetail, setActiveDetail] = useState<VehicleDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [detailsCache, setDetailsCache] = useState<Record<number, VehicleDetail>>({});

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    fetchFavorites()
      .then((res) => setFavorites(res.items))
      .catch((err) => setError(err instanceof Error ? err.message : 'Could not load favorites'))
      .finally(() => setLoading(false));
  }, [user]);

  async function handleMoreInfo(vehicle: VehicleSummary) {
    setActiveSummary(vehicle);
    setDrawerOpen(true);
    setDetailError(null);
    const cached = detailsCache[vehicle.id];
    if (cached) { setActiveDetail(cached); return; }
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

  const handleToggleFavorite = useCallback(async (vehicle: VehicleSummary) => {
    if (!user) { onShowAuth(); return; }
    try {
      if (vehicle.is_favorite) {
        await removeFavorite(vehicle.id);
        setFavorites((prev) => prev.filter((v) => v.id !== vehicle.id));
        toast.success('Removed from favorites');
      } else {
        await addFavorite(vehicle.id);
        setFavorites((prev) => prev.map((v) => v.id === vehicle.id ? { ...v, is_favorite: true } : v));
        toast.success('Added to favorites');
      }
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

  if (!user) {
    return (
      <div className="empty-state">
        <div className="empty-state-icon">🔒</div>
        <h3 className="empty-state-title">Sign in to see your favorites</h3>
        <p className="empty-state-desc">Create an account to save and track your favourite EVs.</p>
        <button type="button" className="btn-primary" onClick={onShowAuth}>Sign in</button>
      </div>
    );
  }

  return (
    <>
      <div className="page-heading">
        <h2 className="page-title">Your Favorites</h2>
        {!loading && <p className="result-count">{favorites.length} saved vehicle{favorites.length !== 1 ? 's' : ''}</p>}
      </div>

      {error ? <p className="error-text">{error}</p> : null}

      <section className="vehicle-grid">
        {loading
          ? Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} />)
          : favorites.map((vehicle) => (
              <VehicleCard
                key={vehicle.id}
                vehicle={vehicle}
                onMoreInfo={handleMoreInfo}
                onToggleFavorite={handleToggleFavorite}
                isLoggedIn
              />
            ))}
      </section>

      {!loading && favorites.length === 0 && !error ? (
        <div className="empty-state">
          <div className="empty-state-icon">♡</div>
          <h3 className="empty-state-title">No favorites yet</h3>
          <p className="empty-state-desc">Browse vehicles and tap the heart to save them here.</p>
          <Link to="/" className="btn-primary" style={{ textDecoration: 'none' }}>Browse vehicles</Link>
        </div>
      ) : null}

      <VehicleDrawer
        open={drawerOpen}
        summary={activeSummary}
        detail={activeDetail}
        loading={loadingDetail}
        error={detailError}
        onClose={() => { setDrawerOpen(false); setActiveSummary(null); setActiveDetail(null); }}
        onToggleFavorite={activeSummary ? () => void handleToggleFavorite(activeSummary) : undefined}
        isLoggedIn
      />
    </>
  );
}
