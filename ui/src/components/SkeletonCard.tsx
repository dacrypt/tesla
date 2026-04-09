import React from 'react';

interface SkeletonCardProps {
  rows?: number;
  showHeader?: boolean;
  showCircle?: boolean;
}

export default function SkeletonCard({ rows = 3, showHeader = true, showCircle = false }: SkeletonCardProps) {
  return (
    <div className="skeleton-card">
      {showHeader && (
        <div className="flex-between mb-md">
          <div className="skeleton skeleton-line-lg" style={{ width: '45%' }} />
          {showCircle && <div className="skeleton skeleton-circle" style={{ width: 32, height: 32 }} />}
        </div>
      )}
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="skeleton skeleton-line"
          style={{ width: `${65 + Math.sin(i * 1.5) * 25}%`, animationDelay: `${i * 0.1}s` }}
        />
      ))}
      <div className="skeleton skeleton-line-sm" style={{ animationDelay: `${rows * 0.1}s` }} />
    </div>
  );
}
