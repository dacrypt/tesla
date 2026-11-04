import React from 'react';
import { useDashboardTiles } from '../../hooks/useDashboardTiles';

/** Show, hide and reorder dashboard tiles (persisted locally). */
const DashboardLayoutCard: React.FC = () => {
  const { allTiles, toggleTile, moveTile, resetTiles } = useDashboardTiles();

  return (
    <div className="tesla-card">
      <p className="section-title">Dashboard Layout</p>
      <p style={{ color: '#999', fontSize: 13, margin: '0 0 12px' }}>Show, hide, and reorder dashboard tiles.</p>
      {allTiles.map((tile, idx) => (
        <div key={tile.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 0', borderBottom: idx < allTiles.length - 1 ? '1px solid #222' : 'none' }}>
          <button
            onClick={() => moveTile(tile.id, 'up')}
            disabled={idx === 0}
            className="tesla-btn secondary"
            style={{ fontSize: 12, padding: '4px 8px', opacity: idx === 0 ? 0.3 : 1, minWidth: 30 }}
          >
            ↑
          </button>
          <button
            onClick={() => moveTile(tile.id, 'down')}
            disabled={idx === allTiles.length - 1}
            className="tesla-btn secondary"
            style={{ fontSize: 12, padding: '4px 8px', opacity: idx === allTiles.length - 1 ? 0.3 : 1, minWidth: 30 }}
          >
            ↓
          </button>
          <label style={{ flex: 1, color: tile.enabled ? '#fff' : '#666', fontSize: 14, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              checked={tile.enabled}
              onChange={() => toggleTile(tile.id)}
              style={{ accentColor: '#05C46B', width: 16, height: 16 }}
            />
            {tile.label}
          </label>
        </div>
      ))}
      <button
        onClick={resetTiles}
        className="tesla-btn secondary"
        style={{ marginTop: 12, fontSize: 13, width: '100%' }}
      >
        Reset to Default
      </button>
    </div>
  );
};

export default DashboardLayoutCard;
