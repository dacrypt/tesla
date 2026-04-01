import React from 'react';

interface SeatHeaterGridProps {
  values: {
    fl: number;
    fr: number;
    rl: number;
    rc: number;
    rr: number;
  };
  onChange: (seat: 'fl' | 'fr' | 'rl' | 'rc' | 'rr', level: number) => void;
  loading?: string | null;
}

const SEAT_LABELS: Record<string, string> = {
  fl: 'Driver',
  fr: 'Pass.',
  rl: 'RL',
  rc: 'RC',
  rr: 'RR',
};

function levelBg(level: number): string {
  if (level === 0) return 'rgba(255,255,255,0.06)';
  if (level === 1) return 'rgba(255,152,0,0.20)';
  if (level === 2) return 'rgba(255,109,0,0.28)';
  return 'rgba(5,196,107,0.28)';
}

function levelBorder(level: number): string {
  if (level === 0) return 'rgba(255,255,255,0.08)';
  if (level === 1) return 'rgba(255,152,0,0.5)';
  if (level === 2) return 'rgba(255,109,0,0.6)';
  return 'rgba(5,196,107,0.6)';
}

function levelIconColor(level: number): string {
  if (level === 0) return '#5a5c60';
  if (level === 1) return '#F99716';
  if (level === 2) return '#ff6d00';
  return '#05C46B';
}

// Simple seat SVG
const SeatSVG = ({ color }: { color: string }) => (
  <svg width={24} height={28} viewBox="0 0 24 28" fill="none">
    {/* Seat back */}
    <rect x={4} y={0} width={16} height={17} rx={4} fill={color} opacity={0.9} />
    {/* Headrest */}
    <rect x={7} y={0} width={10} height={7} rx={3.5} fill={color} />
    {/* Seat base */}
    <rect x={2} y={17} width={20} height={9} rx={3} fill={color} opacity={0.75} />
    {/* Armrest hints */}
    <rect x={0} y={17} width={3} height={7} rx={1.5} fill={color} opacity={0.4} />
    <rect x={21} y={17} width={3} height={7} rx={1.5} fill={color} opacity={0.4} />
  </svg>
);

// Level dots
const LevelDots = ({ level, color }: { level: number; color: string }) => (
  <div style={{ display: 'flex', gap: 3, justifyContent: 'center' }}>
    {[1, 2, 3].map((d) => (
      <div
        key={d}
        style={{
          width: 5,
          height: 5,
          borderRadius: '50%',
          background: d <= level ? color : 'rgba(255,255,255,0.12)',
          transition: 'background 0.2s',
        }}
      />
    ))}
  </div>
);

// Spinner
function Spinner() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.12)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#F99716" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

interface SeatButtonProps {
  seatKey: 'fl' | 'fr' | 'rl' | 'rc' | 'rr';
  level: number;
  isLoading: boolean;
  onPress: () => void;
}

const SeatButton: React.FC<SeatButtonProps> = ({ seatKey, level, isLoading, onPress }) => {
  const iconColor = levelIconColor(level);
  return (
    <button
      className="seat-btn"
      onClick={onPress}
      disabled={isLoading}
      style={{
        background: levelBg(level),
        borderColor: levelBorder(level),
        boxShadow: level > 0 ? `0 0 12px ${levelBorder(level)}` : 'none',
      }}
    >
      {isLoading ? (
        <Spinner />
      ) : (
        <SeatSVG color={iconColor} />
      )}
      <LevelDots level={level} color={iconColor} />
      <span
        className="seat-label"
        style={{ color: level > 0 ? '#ffffff' : '#86888f' }}
      >
        {SEAT_LABELS[seatKey]}
      </span>
    </button>
  );
};

const SeatHeaterGrid: React.FC<SeatHeaterGridProps> = ({ values, onChange, loading }) => {
  const cycle = (seat: 'fl' | 'fr' | 'rl' | 'rc' | 'rr') => {
    onChange(seat, (values[seat] + 1) % 4);
  };

  return (
    <div>
      {/* Front row */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
        <SeatButton seatKey="fl" level={values.fl} isLoading={loading === 'fl'} onPress={() => cycle('fl')} />
        {/* Center console gap */}
        <div style={{ flex: 0.4 }} />
        <SeatButton seatKey="fr" level={values.fr} isLoading={loading === 'fr'} onPress={() => cycle('fr')} />
      </div>
      {/* Rear row */}
      <div style={{ display: 'flex', gap: 8 }}>
        <SeatButton seatKey="rl" level={values.rl} isLoading={loading === 'rl'} onPress={() => cycle('rl')} />
        <SeatButton seatKey="rc" level={values.rc} isLoading={loading === 'rc'} onPress={() => cycle('rc')} />
        <SeatButton seatKey="rr" level={values.rr} isLoading={loading === 'rr'} onPress={() => cycle('rr')} />
      </div>
      <p style={{ color: '#86888f', fontSize: 11, textAlign: 'center', marginTop: 10, marginBottom: 0 }}>
        Tap seat to cycle: Off → Low → Med → High
      </p>
    </div>
  );
};

export default SeatHeaterGrid;
