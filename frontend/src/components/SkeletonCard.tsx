export function SkeletonCard() {
  return (
    <article className="vehicle-card skeleton-card" aria-hidden="true">
      <div className="skeleton skeleton-image" />
      <div className="vehicle-card-content">
        <div className="skeleton skeleton-title" />
        <div className="skeleton skeleton-subtitle" />
        <div className="vehicle-quick-specs">
          <div className="skeleton skeleton-badge" />
          <div className="skeleton skeleton-badge" />
          <div className="skeleton skeleton-badge" />
        </div>
        <div className="card-actions">
          <div className="skeleton skeleton-btn" />
          <div className="skeleton skeleton-btn-sm" />
        </div>
      </div>
    </article>
  );
}
