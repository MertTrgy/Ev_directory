type Props = {
  onReset: () => void;
  message?: string;
};

export function EmptyState({ onReset, message = 'No vehicles found' }: Props) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">🔍</div>
      <h3 className="empty-state-title">{message}</h3>
      <p className="empty-state-desc">Try adjusting your filters or search term.</p>
      <button type="button" className="btn-primary" onClick={onReset}>
        Clear filters
      </button>
    </div>
  );
}
