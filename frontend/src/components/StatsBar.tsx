import { useEffect, useState } from 'react';
import { fetchStats } from '../api';
import type { StatsResponse } from '../types';

export function StatsBar() {
  const [stats, setStats] = useState<StatsResponse | null>(null);

  useEffect(() => {
    fetchStats().then(setStats).catch(() => {});
  }, []);

  if (!stats) return null;

  const items = [
    { value: stats.total_vehicles.toLocaleString(), label: 'Vehicles' },
    { value: stats.total_brands.toLocaleString(), label: 'Brands' },
    { value: stats.total_markets.toLocaleString(), label: 'Markets' },
    stats.avg_range_km != null ? { value: `${Math.round(stats.avg_range_km)} km`, label: 'Avg range' } : null,
    stats.max_range_km != null ? { value: `${stats.max_range_km} km`, label: 'Best range' } : null,
  ].filter(Boolean) as { value: string; label: string }[];

  return (
    <div className="stats-bar">
      {items.map((item) => (
        <div key={item.label} className="stat-item">
          <span className="stat-value">{item.value}</span>
          <span className="stat-label">{item.label}</span>
        </div>
      ))}
    </div>
  );
}
