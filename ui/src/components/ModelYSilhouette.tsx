import React from 'react';

interface ModelYSilhouetteProps {
  locked?: boolean;
  chargingState?: string;
  batteryPercent?: number;
  climateOn?: boolean;
  trunkOpen?: boolean;
  frunkOpen?: boolean;
}

// Lock icon SVG path
const LockIcon = ({ open }: { open: boolean }) =>
  open ? (
    // unlocked
    <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.65 1.35-3 3-3s3 1.35 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/>
    </svg>
  ) : (
    // locked
    <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
      <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/>
    </svg>
  );

const ModelYSilhouette: React.FC<ModelYSilhouetteProps> = ({
  locked = true,
  chargingState,
  batteryPercent,
  climateOn = false,
  trunkOpen = false,
  frunkOpen = false,
}) => {
  const isCharging = chargingState === 'Charging';

  const batteryColor =
    batteryPercent == null ? '#86888f'
    : batteryPercent > 50 ? '#0BE881'
    : batteryPercent > 20 ? '#F99716'
    : '#05C46B';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '12px 0 4px' }}>
      {/* Top-down Model Y SVG — viewBox 320x200 */}
      <svg
        viewBox="0 0 320 200"
        width="100%"
        style={{ maxWidth: 320, filter: 'drop-shadow(0 6px 24px rgba(0,0,0,0.6))' }}
      >
        {/* ===== WHEELS ===== */}
        {/* Front-left */}
        <rect x={34} y={38} width={28} height={46} rx={7} fill="#0d0e10" stroke="#3d3f43" strokeWidth={1.5} />
        <rect x={39} y={46} width={18} height={30} rx={4} fill="#232529" />
        {/* Front-right */}
        <rect x={258} y={38} width={28} height={46} rx={7} fill="#0d0e10" stroke="#3d3f43" strokeWidth={1.5} />
        <rect x={263} y={46} width={18} height={30} rx={4} fill="#232529" />
        {/* Rear-left */}
        <rect x={34} y={116} width={28} height={46} rx={7} fill="#0d0e10" stroke="#3d3f43" strokeWidth={1.5} />
        <rect x={39} y={124} width={18} height={30} rx={4} fill="#232529" />
        {/* Rear-right */}
        <rect x={258} y={116} width={28} height={46} rx={7} fill="#0d0e10" stroke="#3d3f43" strokeWidth={1.5} />
        <rect x={263} y={124} width={18} height={30} rx={4} fill="#232529" />

        {/* ===== MAIN BODY ===== */}
        <path
          d={`
            M 70 44
            Q 72 26 100 22
            L 220 22
            Q 248 26 250 44
            L 270 80
            Q 276 100 276 120
            L 274 158
            Q 270 172 252 174
            L 68 174
            Q 50 172 46 158
            L 44 120
            Q 44 100 50 80
            Z
          `}
          fill="#252930"
          stroke="rgba(255,255,255,0.14)"
          strokeWidth={1.5}
        />

        {/* ===== FRUNK area (front hood) ===== */}
        <path
          d={`M 82 44 L 238 44 L 248 60 Q 245 70 160 72 Q 75 70 72 60 Z`}
          fill={frunkOpen ? 'rgba(249,151,22,0.25)' : 'rgba(255,255,255,0.03)'}
          stroke={frunkOpen ? '#F99716' : 'rgba(255,255,255,0.06)'}
          strokeWidth={1}
        />

        {/* ===== WINDSHIELD ===== */}
        <path
          d={`M 88 44 Q 96 26 160 24 Q 224 26 232 44 L 238 60 Q 220 55 160 54 Q 100 55 82 60 Z`}
          fill="rgba(26,58,92,0.7)"
          stroke="rgba(33,150,243,0.3)"
          strokeWidth={0.8}
        />

        {/* ===== ROOF (panoramic sunroof area) ===== */}
        <rect
          x={92} y={72} width={136} height={56}
          rx={8}
          fill="rgba(255,255,255,0.04)"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={1}
        />

        {/* ===== REAR WINDOW ===== */}
        <path
          d={`M 92 136 Q 96 155 160 158 Q 224 155 228 136 L 228 128 Q 210 132 160 133 Q 110 132 92 128 Z`}
          fill="rgba(26,58,92,0.5)"
          stroke="rgba(15,188,249,0.2)"
          strokeWidth={0.8}
        />

        {/* ===== TRUNK area ===== */}
        <path
          d={`M 82 156 L 238 156 L 248 144 Q 245 138 160 136 Q 75 138 72 144 Z`}
          fill={trunkOpen ? 'rgba(249,151,22,0.25)' : 'rgba(255,255,255,0.03)'}
          stroke={trunkOpen ? '#F99716' : 'rgba(255,255,255,0.06)'}
          strokeWidth={1}
        />

        {/* ===== DOOR LINES ===== */}
        <line x1={160} y1={70} x2={160} y2={132} stroke="rgba(255,255,255,0.07)" strokeWidth={1} />
        <line x1={68} y1={100} x2={252} y2={100} stroke="rgba(255,255,255,0.07)" strokeWidth={1} />

        {/* ===== DOOR HANDLES ===== */}
        {[102, 178].map((y, i) => (
          <React.Fragment key={i}>
            <rect x={54} y={y} width={14} height={4} rx={2} fill={locked ? '#3d3f43' : '#05C46B'} opacity={0.9} />
            <rect x={252} y={y} width={14} height={4} rx={2} fill={locked ? '#3d3f43' : '#05C46B'} opacity={0.9} />
          </React.Fragment>
        ))}

        {/* ===== HEADLIGHTS ===== */}
        <path d="M 84 44 Q 90 30 110 26 L 112 30 Q 94 34 88 48 Z" fill="#fff" opacity={0.12} />
        <path d="M 236 44 Q 230 30 210 26 L 208 30 Q 226 34 232 48 Z" fill="#fff" opacity={0.12} />

        {/* ===== TAILLIGHTS ===== */}
        <path d="M 84 156 Q 92 166 112 170 L 112 166 Q 95 163 88 155 Z" fill="#05C46B" opacity={0.45} />
        <path d="M 236 156 Q 228 166 208 170 L 208 166 Q 225 163 232 155 Z" fill="#05C46B" opacity={0.45} />

        {/* ===== CHARGING PORT (left side, rear) ===== */}
        <circle
          cx={46}
          cy={138}
          r={isCharging ? 7 : 5}
          fill={isCharging ? '#0BE881' : 'rgba(255,255,255,0.15)'}
          stroke={isCharging ? '#0BE881' : 'rgba(255,255,255,0.1)'}
          strokeWidth={1}
        >
          {isCharging && (
            <animate attributeName="opacity" values="1;0.4;1" dur="1.4s" repeatCount="indefinite" />
          )}
        </circle>
        {/* Lightning bolt in port */}
        {isCharging && (
          <text x={46} y={142} textAnchor="middle" fill="#000" fontSize={7} fontWeight="bold">&#9889;</text>
        )}

        {/* ===== CHARGING ARC (animated dashed arc when charging) ===== */}
        {isCharging && (
          <path
            d="M 44 120 A 30 30 0 0 1 44 138"
            fill="none"
            stroke="#0BE881"
            strokeWidth={2.5}
            strokeDasharray="6 4"
            strokeLinecap="round"
            opacity={0.7}
          >
            <animate attributeName="stroke-dashoffset" from="0" to="-20" dur="0.8s" repeatCount="indefinite" />
          </path>
        )}

        {/* ===== CLIMATE INDICATOR ===== */}
        {climateOn && (
          <g>
            <circle cx={274} cy={90} r={9} fill="rgba(15,188,249,0.2)" stroke="rgba(15,188,249,0.4)" strokeWidth={1} />
            <text x={274} y={94} textAnchor="middle" fill="#0FBCF9" fontSize={10} fontWeight="bold">~</text>
          </g>
        )}

        {/* ===== BATTERY % text in center ===== */}
        {batteryPercent != null && (
          <>
            <text
              x={160}
              y={107}
              textAnchor="middle"
              fill={batteryColor}
              fontSize={28}
              fontWeight="700"
              fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
              letterSpacing={-1}
            >
              {Math.round(batteryPercent)}
            </text>
            <text
              x={160}
              y={120}
              textAnchor="middle"
              fill="rgba(255,255,255,0.35)"
              fontSize={10}
              fontFamily="-apple-system, BlinkMacSystemFont, sans-serif"
            >
              %
            </text>
          </>
        )}
      </svg>

      {/* ===== STATUS BADGES BELOW ===== */}
      <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        {/* Lock status */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 5,
            background: 'rgba(255,255,255,0.06)',
            border: `1px solid ${locked ? 'rgba(255,255,255,0.1)' : 'rgba(5,196,107,0.4)'}`,
            borderRadius: 20,
            padding: '5px 10px',
            fontSize: 12,
            color: locked ? '#86888f' : '#05C46B',
            fontWeight: 500,
          }}
        >
          <LockIcon open={!locked} />
          {locked ? 'Locked' : 'Unlocked'}
        </div>

        {/* Charging badge */}
        {isCharging && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'rgba(11,232,129,0.1)',
              border: '1px solid rgba(11,232,129,0.35)',
              borderRadius: 20,
              padding: '5px 10px',
              fontSize: 12,
              color: '#0BE881',
              fontWeight: 600,
            }}
          >
            <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor">
              <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
            </svg>
            Charging
          </div>
        )}

        {/* Climate badge */}
        {climateOn && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'rgba(33,150,243,0.1)',
              border: '1px solid rgba(15,188,249,0.35)',
              borderRadius: 20,
              padding: '5px 10px',
              fontSize: 12,
              color: '#0FBCF9',
              fontWeight: 500,
            }}
          >
            <svg width={12} height={12} viewBox="0 0 24 24" fill="currentColor">
              <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z"/>
            </svg>
            Climate
          </div>
        )}

        {/* Trunk open */}
        {trunkOpen && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'rgba(249,151,22,0.1)',
              border: '1px solid rgba(249,151,22,0.35)',
              borderRadius: 20,
              padding: '5px 10px',
              fontSize: 12,
              color: '#F99716',
              fontWeight: 500,
            }}
          >
            Trunk Open
          </div>
        )}

        {/* Frunk open */}
        {frunkOpen && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              background: 'rgba(249,151,22,0.1)',
              border: '1px solid rgba(249,151,22,0.35)',
              borderRadius: 20,
              padding: '5px 10px',
              fontSize: 12,
              color: '#F99716',
              fontWeight: 500,
            }}
          >
            Frunk Open
          </div>
        )}
      </div>
    </div>
  );
};

export default ModelYSilhouette;
