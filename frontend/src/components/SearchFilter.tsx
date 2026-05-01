import { DEFAULT_FILTERS, type SearchFilters } from '../types';

type Props = {
  filters: SearchFilters;
  onChange: (filters: SearchFilters) => void;
  onReset: () => void;
};

const BODY_STYLES = ['', 'SUV', 'Saloon', 'Hatchback', 'Estate', 'Coupe', 'Convertible', 'Van', 'Pickup'];
const DRIVETRAINS = ['', 'rwd', 'fwd', 'awd'];
const SORT_OPTIONS = [
  { value: 'updated', label: 'Last updated' },
  { value: 'name', label: 'Name' },
  { value: 'year', label: 'Year' },
  { value: 'range', label: 'Range' },
  { value: 'power', label: 'Power' },
];

export function SearchFilter({ filters, onChange, onReset }: Props) {
  function set(key: keyof SearchFilters, value: string) {
    onChange({ ...filters, [key]: value });
  }

  const hasFilters = Object.entries(filters).some(
    ([k, v]) => v !== '' && v !== DEFAULT_FILTERS[k as keyof SearchFilters],
  );

  return (
    <div className="search-filter-bar">
      <div className="search-row">
        <input
          type="search"
          className="search-input"
          placeholder="Search vehicles…"
          value={filters.search}
          onChange={(e) => set('search', e.target.value)}
        />
        <input
          type="text"
          className="filter-input"
          placeholder="Brand"
          value={filters.brand}
          onChange={(e) => set('brand', e.target.value)}
        />
        <input
          type="text"
          className="filter-input"
          placeholder="Market"
          value={filters.market}
          onChange={(e) => set('market', e.target.value)}
        />
      </div>

      <div className="filter-row">
        <div className="filter-group">
          <label className="filter-label">Year</label>
          <div className="range-inputs">
            <input type="number" className="filter-input-sm" placeholder="From" value={filters.year_min} onChange={(e) => set('year_min', e.target.value)} min="2000" max="2030" />
            <span>–</span>
            <input type="number" className="filter-input-sm" placeholder="To" value={filters.year_max} onChange={(e) => set('year_max', e.target.value)} min="2000" max="2030" />
          </div>
        </div>

        <div className="filter-group">
          <label className="filter-label">Range (km)</label>
          <div className="range-inputs">
            <input type="number" className="filter-input-sm" placeholder="Min" value={filters.range_min_km} onChange={(e) => set('range_min_km', e.target.value)} min="0" />
            <span>–</span>
            <input type="number" className="filter-input-sm" placeholder="Max" value={filters.range_max_km} onChange={(e) => set('range_max_km', e.target.value)} min="0" />
          </div>
        </div>

        <div className="filter-group">
          <label className="filter-label">Body style</label>
          <select className="filter-select" value={filters.body_style} onChange={(e) => set('body_style', e.target.value)}>
            {BODY_STYLES.map((s) => <option key={s} value={s}>{s || 'Any'}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label">Drivetrain</label>
          <select className="filter-select" value={filters.drivetrain} onChange={(e) => set('drivetrain', e.target.value)}>
            {DRIVETRAINS.map((d) => <option key={d} value={d}>{d ? d.toUpperCase() : 'Any'}</option>)}
          </select>
        </div>

        <div className="filter-group">
          <label className="filter-label">Sort by</label>
          <div className="sort-row">
            <select className="filter-select" value={filters.sort_by} onChange={(e) => set('sort_by', e.target.value)}>
              {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
            <button
              type="button"
              className="sort-dir-btn"
              title={filters.order === 'desc' ? 'Descending' : 'Ascending'}
              onClick={() => set('order', filters.order === 'desc' ? 'asc' : 'desc')}
            >
              {filters.order === 'desc' ? '↓' : '↑'}
            </button>
          </div>
        </div>

        {hasFilters ? (
          <button type="button" className="btn-ghost reset-btn" onClick={onReset}>
            Reset
          </button>
        ) : null}
      </div>
    </div>
  );
}
