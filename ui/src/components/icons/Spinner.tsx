import React from 'react';

interface SpinnerProps {
  size?: number;
  color?: string;
  trackOpacity?: number;
}

export default function Spinner({ size = 20, color = '#05C46B', trackOpacity = 0.15 }: SpinnerProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
      <circle cx={12} cy={12} r={9} stroke={`rgba(255,255,255,${trackOpacity})`} strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke={color} strokeWidth={3} strokeLinecap="round">
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.8s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );
}
