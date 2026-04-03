import React from 'react';

const DashboardPanel = ({ title, metrics = [], chartData = null }) => {
  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: '8px',
      padding: '16px',
      margin: '8px 0',
      backgroundColor: '#ffffff'
    }}>
      {title && (
        <h3 style={{
          margin: '0 0 16px 0',
          fontSize: '16px',
          fontWeight: 600,
          color: '#111827'
        }}>
          {title}
        </h3>
      )}
      
      {/* Metrics grid */}
      {metrics.length > 0 && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
          gap: '12px',
          marginBottom: chartData ? '16px' : '0'
        }}>
          {metrics.map((metric, idx) => (
            <div key={idx} style={{
              padding: '12px',
              backgroundColor: '#f9fafb',
              borderRadius: '6px',
              border: '1px solid #e5e7eb'
            }}>
              <div style={{
                fontSize: '11px',
                color: '#6b7280',
                marginBottom: '4px',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                {metric.label}
              </div>
              <div style={{
                fontSize: '20px',
                fontWeight: 700,
                color: '#111827'
              }}>
                {metric.value}
              </div>
              {metric.change && (
                <div style={{
                  fontSize: '11px',
                  color: metric.change > 0 ? '#10b981' : '#ef4444',
                  marginTop: '2px'
                }}>
                  {metric.change > 0 ? '↑' : '↓'} {Math.abs(metric.change)}%
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      
      {/* Simple bar chart */}
      {chartData && (
        <div style={{ marginTop: '16px' }}>
          {chartData.map((item, idx) => (
            <div key={idx} style={{ marginBottom: '8px' }}>
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                fontSize: '12px',
                marginBottom: '4px'
              }}>
                <span style={{ color: '#374151' }}>{item.label}</span>
                <span style={{ fontWeight: 600, color: '#111827' }}>{item.value}</span>
              </div>
              <div style={{
                width: '100%',
                height: '6px',
                backgroundColor: '#e5e7eb',
                borderRadius: '3px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${(item.value / Math.max(...chartData.map(d => d.value))) * 100}%`,
                  height: '100%',
                  backgroundColor: item.color || '#3b82f6',
                  transition: 'width 0.3s ease'
                }} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default DashboardPanel;
