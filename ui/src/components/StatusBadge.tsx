import React from 'react';

interface StatusBadgeProps {
  state: string | undefined;
  showLabel?: boolean;
  size?: number;
}

function getStatusColor(state: string | undefined): string {
  if (!state) return '#86888f';
  switch (state.toLowerCase()) {
    case 'online': return '#0BE881';
    case 'asleep':
    case 'sleeping': return '#F99716';
    case 'charging': return '#0FBCF9';
    case 'offline':
    case 'unknown':
    default: return '#86888f';
  }
}

function getStatusLabel(state: string | undefined): string {
  if (!state) return 'Unknown';
  return state.charAt(0).toUpperCase() + state.slice(1).toLowerCase();
}

const StatusBadge: React.FC<StatusBadgeProps> = ({ state, showLabel = true, size = 7 }) => {
  const color = getStatusColor(state);
  const label = getStatusLabel(state);
  const cls = label.toLowerCase();

  return (
    <span className={`status-pill ${cls}`}>
      <span
        style={{
          display: 'inline-block',
          width: size,
          height: size,
          borderRadius: '50%',
          background: color,
          flexShrink: 0,
          boxShadow: `0 0 5px ${color}`,
        }}
      />
      {showLabel && label}
    </span>
  );
};

export default StatusBadge;
