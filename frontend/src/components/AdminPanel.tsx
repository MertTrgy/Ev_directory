import { useState } from 'react';
import { fetchEnrichStatus, fetchHealth, triggerEnrichAll, triggerSync } from '../api';

type Props = { onClose: () => void };

type OpResult = { ok: boolean; message: string } | null;

export function AdminPanel({ onClose }: Props) {
  const [results, setResults] = useState<Record<string, OpResult>>({});
  const [running, setRunning] = useState<Record<string, boolean>>({});

  async function run(key: string, fn: () => Promise<unknown>) {
    setRunning((r) => ({ ...r, [key]: true }));
    try {
      const res = await fn();
      setResults((r) => ({ ...r, [key]: { ok: true, message: JSON.stringify(res, null, 2) } }));
    } catch (e) {
      setResults((r) => ({ ...r, [key]: { ok: false, message: e instanceof Error ? e.message : 'Error' } }));
    } finally {
      setRunning((r) => ({ ...r, [key]: false }));
    }
  }

  const ops = [
    { key: 'health', label: 'Health check', fn: fetchHealth },
    { key: 'sync', label: 'Sync JSON → DB', fn: triggerSync },
    { key: 'enrich', label: 'Start image enrichment', fn: triggerEnrichAll },
    { key: 'enrichStatus', label: 'Enrichment status', fn: fetchEnrichStatus },
  ];

  return (
    <div className="modal-backdrop" onClick={onClose} role="presentation">
      <div className="modal-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <header className="modal-header">
          <h2>Admin panel</h2>
          <button type="button" className="drawer-close-button" onClick={onClose}>✕</button>
        </header>

        <div className="admin-ops">
          {ops.map((op) => (
            <div key={op.key} className="admin-op-row">
              <button
                type="button"
                className="btn-primary admin-op-btn"
                disabled={running[op.key]}
                onClick={() => void run(op.key, op.fn)}
              >
                {running[op.key] ? 'Running…' : op.label}
              </button>
              {results[op.key] ? (
                <pre className={`admin-result ${results[op.key]!.ok ? 'ok' : 'error'}`}>
                  {results[op.key]!.message}
                </pre>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
