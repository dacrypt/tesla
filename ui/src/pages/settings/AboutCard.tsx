import React from 'react';

const AboutCard: React.FC = () => {
  return (
    <div className="tesla-card" style={{ textAlign: 'center', padding: '24px 16px' }}>
      <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#05C46B', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', boxShadow: '0 4px 16px rgba(5,196,107,0.35)' }}>
        <svg width={28} height={28} viewBox="0 0 24 24" fill="white">
          <path d="M12 3l-4 5h3v5H7l5 8 5-8h-4V8h3z"/>
        </svg>
      </div>
      <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 18, letterSpacing: '-0.3px' }}>Tesla Control</div>
      <div style={{ color: '#86888f', fontSize: 13, marginTop: 4 }}>Companion app for tesla-cli</div>
      <div style={{ color: '#86888f', fontSize: 12, marginTop: 6, opacity: 0.5 }}>v1.0.0</div>
    </div>
  );
};

export default AboutCard;
