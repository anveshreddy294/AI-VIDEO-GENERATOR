import React from 'react';

/**
 * VISUALAI : MANDATORY SKELETON LOADER ARCHITECTURE
 * Layout-stable, restrained shimmer without harsh gradients or neon
 */

export function SkeletonBox({ width = '100%', height = '20px', className = '', style = {} }) {
  return (
    <div 
      className={`atelier-skeleton-box ${className}`}
      style={{
        width,
        height,
        backgroundColor: 'var(--surface-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-sharp)',
        opacity: 0.75,
        animation: 'atelierShimmer 1.8s ease-in-out infinite',
        ...style
      }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 3, gap = '8px', className = '' }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap }} className={className} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonBox 
          key={i} 
          height="14px" 
          width={i === lines - 1 ? '65%' : '100%'} 
        />
      ))}
    </div>
  );
}

export function SkeletonCard({ height = '180px', className = '' }) {
  return (
    <div 
      className={`atelier-skeleton-card ${className}`}
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        padding: '16px',
        backgroundColor: 'var(--surface-panel)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-card)',
        height
      }}
      aria-hidden="true"
    >
      <SkeletonBox height="18px" width="40%" />
      <SkeletonBox height="60px" width="100%" />
      <div style={{ marginTop: 'auto', display: 'flex', justifyContent: 'space-between' }}>
        <SkeletonBox height="14px" width="30%" />
        <SkeletonBox height="14px" width="20%" />
      </div>
    </div>
  );
}
