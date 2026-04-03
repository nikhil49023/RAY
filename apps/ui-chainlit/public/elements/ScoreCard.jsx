import React from 'react';

const ScoreCard = ({ ready, total, services, style = 'minimal' }) => {
  const percentage = total > 0 ? (ready / total) * 100 : 0;
  
  const getColor = () => {
    if (style === 'executive') return percentage > 70 ? '#2563eb' : '#be123c';
    if (style === 'diagnostic') return percentage > 70 ? '#16a34a' : '#b91c1c';
    return percentage > 70 ? '#0f766e' : '#b91c1c';
  };
  
  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: '8px',
      padding: '16px',
      margin: '8px 0',
      backgroundColor: '#f9fafb'
    }}>
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '12px'
      }}>
        <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>
          Runtime Health
        </h3>
        <span style={{
          fontSize: '24px',
          fontWeight: 700,
          color: getColor()
        }}>
          {ready}/{total}
        </span>
      </div>
      
      <div style={{
        width: '100%',
        height: '8px',
        backgroundColor: '#e5e7eb',
        borderRadius: '4px',
        overflow: 'hidden'
      }}>
        <div style={{
          width: `${percentage}%`,
          height: '100%',
          backgroundColor: getColor(),
          transition: 'width 0.3s ease'
        }} />
      </div>
      
      <div style={{
        marginTop: '12px',
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))',
        gap: '8px'
      }}>
        {services && services.map((service, idx) => (
          <div key={idx} style={{
            display: 'flex',
            alignItems: 'center',
            fontSize: '12px'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: service.ready ? '#10b981' : '#ef4444',
              marginRight: '6px'
            }} />
            <span>{service.name}</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default ScoreCard;
