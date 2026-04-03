import React from 'react';

const ResearchTimeline = ({ nodes = [] }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed': return '#10b981';
      case 'running': return '#3b82f6';
      case 'pending': return '#9ca3af';
      case 'failed': return '#ef4444';
      default: return '#9ca3af';
    }
  };
  
  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed': return '✓';
      case 'running': return '⟳';
      case 'pending': return '○';
      case 'failed': return '✗';
      default: return '○';
    }
  };
  
  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: '8px',
      padding: '16px',
      margin: '8px 0',
      backgroundColor: '#ffffff'
    }}>
      <h3 style={{
        margin: '0 0 16px 0',
        fontSize: '14px',
        fontWeight: 600,
        color: '#374151'
      }}>
        Execution Timeline
      </h3>
      
      <div style={{ position: 'relative' }}>
        {/* Vertical line */}
        <div style={{
          position: 'absolute',
          left: '12px',
          top: '8px',
          bottom: '8px',
          width: '2px',
          backgroundColor: '#e5e7eb'
        }} />
        
        {/* Nodes */}
        {nodes.map((node, idx) => (
          <div key={idx} style={{
            display: 'flex',
            alignItems: 'flex-start',
            marginBottom: '16px',
            position: 'relative'
          }}>
            {/* Status indicator */}
            <div style={{
              width: '24px',
              height: '24px',
              borderRadius: '50%',
              backgroundColor: getStatusColor(node.status),
              color: '#ffffff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '12px',
              fontWeight: 600,
              marginRight: '12px',
              zIndex: 1,
              flexShrink: 0
            }}>
              {getStatusIcon(node.status)}
            </div>
            
            {/* Node info */}
            <div style={{ flex: 1 }}>
              <div style={{
                fontSize: '13px',
                fontWeight: 600,
                color: '#111827',
                marginBottom: '2px'
              }}>
                {node.name}
              </div>
              {node.detail && (
                <div style={{
                  fontSize: '12px',
                  color: '#6b7280'
                }}>
                  {node.detail}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ResearchTimeline;
