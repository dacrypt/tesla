import React from 'react';

interface CommandButtonProps {
  icon: React.ReactNode;
  label: string;
  sublabel?: string;
  onClick: () => void;
  loading?: boolean;
  active?: boolean;
  color?: 'default' | 'red' | 'green' | 'blue' | 'orange';
  disabled?: boolean;
}

const iconBg: Record<string, string> = {
  default: 'rgba(255,255,255,0.1)',
  red: '#05C46B',
  green: '#0BE881',
  blue: '#0FBCF9',
  orange: '#F99716',
};

const iconActiveBg: Record<string, string> = {
  default: 'rgba(255,255,255,0.18)',
  red: '#05C46B',
  green: '#0BE881',
  blue: '#0FBCF9',
  orange: '#F99716',
};

// Inline spinner SVG to avoid IonSpinner color issues
function Spinner({ color }: { color: string }) {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.15)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke={color} strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

const CommandButton: React.FC<CommandButtonProps> = ({
  icon,
  label,
  sublabel,
  onClick,
  loading = false,
  active = false,
  color = 'default',
  disabled = false,
}) => {
  const bg = active ? iconActiveBg[color] : iconBg[color];

  return (
    <button
      className={`action-btn${active ? ' active' : ''}`}
      onClick={onClick}
      disabled={loading || disabled}
      style={{ opacity: disabled ? 0.45 : 1 }}
    >
      <div
        className="icon-circle"
        style={{
          background: bg,
          boxShadow: active ? `0 0 14px ${bg}80` : 'none',
        }}
      >
        {loading ? (
          <Spinner color={iconBg[color === 'default' ? 'default' : color]} />
        ) : (
          <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: color === 'default' ? '#ffffff' : '#000000' }}>
            {icon}
          </span>
        )}
      </div>
      <span className="btn-label">{label}</span>
      {sublabel && (
        <span style={{ color: '#86888f', fontSize: 10, textAlign: 'center' }}>{sublabel}</span>
      )}
    </button>
  );
};

export default CommandButton;
