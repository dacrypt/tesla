import React from 'react';

interface BatteryGaugeProps {
  percent: number;
  limit?: number;
  range?: number;
  size?: number;
  showLabel?: boolean;
  offline?: boolean;
}

const BatteryGauge: React.FC<BatteryGaugeProps> = ({
  percent,
  limit,
  range,
  size = 200,
  showLabel = true,
  offline = false,
}) => {
  const cx = size / 2;
  const cy = size / 2 + size * 0.06; // shift center down slightly so arc fits
  const radius = (size / 2) * 0.76;
  const strokeWidth = Math.max(12, size * 0.075);

  // Arc spans 220 degrees: from 160° to 20° (clockwise, going through bottom)
  const startAngle = 160;
  const totalAngle = 220;
  const endAngle = startAngle + totalAngle; // 380 = wrap to 20°

  function polarToXY(angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return {
      x: cx + radius * Math.cos(rad),
      y: cy + radius * Math.sin(rad),
    };
  }

  function arcPath(fromDeg: number, toDeg: number): string {
    const s = polarToXY(fromDeg);
    const e = polarToXY(toDeg);
    const span = toDeg - fromDeg;
    const large = span > 180 ? 1 : 0;
    return `M ${s.x.toFixed(2)} ${s.y.toFixed(2)} A ${radius} ${radius} 0 ${large} 1 ${e.x.toFixed(2)} ${e.y.toFixed(2)}`;
  }

  const clampedPct = Math.max(0, Math.min(100, percent));
  const fillEndAngle = startAngle + (clampedPct / 100) * totalAngle;
  const limitAngle = limit != null ? startAngle + (limit / 100) * totalAngle : null;

  const fillColor =
    offline ? '#86888f' :
    clampedPct > 50 ? '#0BE881' : clampedPct > 20 ? '#F99716' : '#FF6B6B';

  const limitPt = limitAngle != null ? polarToXY(limitAngle) : null;

  return (
    <div style={{ position: 'relative', width: size, height: size, margin: '0 auto' }}>
      <svg width={size} height={size} style={{ overflow: 'visible' }}>
        {/* Track */}
        <path
          d={arcPath(startAngle, startAngle + totalAngle)}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Fill */}
        {clampedPct > 0 && (
          <path
            d={arcPath(startAngle, fillEndAngle)}
            fill="none"
            stroke={fillColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            style={{
              filter: `drop-shadow(0 0 6px ${fillColor}60)`,
              transition: 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
          />
        )}
        {/* Limit marker circle */}
        {limitPt && (
          <circle
            cx={limitPt.x}
            cy={limitPt.y}
            r={strokeWidth * 0.55}
            fill="#0FBCF9"
            stroke="#1a1d23"
            strokeWidth={2}
          />
        )}
      </svg>

      {showLabel && (
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -42%)',
            textAlign: 'center',
            pointerEvents: 'none',
          }}
        >
          <div
            style={{
              fontSize: offline ? size * 0.18 : size * 0.23,
              fontWeight: 700,
              color: fillColor,
              lineHeight: 1,
              letterSpacing: '-2px',
              transition: 'color 0.4s',
            }}
          >
            {offline ? '--' : Math.round(clampedPct)}
          </div>
          <div style={{ fontSize: size * 0.08, color: '#86888f', fontWeight: 500, marginTop: 1 }}>
            {offline ? '' : '%'}
          </div>
          {range != null && (
            <div style={{ fontSize: size * 0.072, color: '#86888f', marginTop: 4 }}>
              {Math.round(range)} mi
            </div>
          )}
          {limit != null && (
            <div style={{ fontSize: size * 0.065, color: '#0FBCF9', marginTop: 2, opacity: 0.8 }}>
              Limit {limit}%
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default BatteryGauge;
