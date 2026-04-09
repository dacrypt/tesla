import React, { useState } from 'react';

const CopyIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
  </svg>
);

const CheckIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="#05C46B">
    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
  </svg>
);

export default function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand('copy');
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <button
      onClick={handleCopy}
      title={copied ? 'Copied!' : (label || 'Copy to clipboard')}
      aria-label={copied ? 'Copied!' : (label || 'Copy to clipboard')}
      style={{
        display: 'inline-flex', alignItems: 'center', gap: 4,
        background: 'none', border: '1px solid rgba(255,255,255,0.1)',
        borderRadius: 8, padding: '4px 10px', cursor: 'pointer',
        color: copied ? '#05C46B' : '#86888f',
        fontSize: 11, fontWeight: 600,
        transition: 'all 0.2s ease',
      }}
    >
      {copied ? <CheckIcon /> : <CopyIcon />}
      {copied ? 'Copied' : (label || 'Copy')}
    </button>
  );
}
