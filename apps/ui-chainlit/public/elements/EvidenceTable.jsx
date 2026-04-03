import React from 'react';

const EvidenceTable = ({ evidence = [] }) => {
  if (!evidence || evidence.length === 0) {
    return null;
  }
  
  return (
    <div style={{
      border: '1px solid #e5e7eb',
      borderRadius: '8px',
      padding: '16px',
      margin: '8px 0',
      backgroundColor: '#ffffff'
    }}>
      <h3 style={{
        margin: '0 0 12px 0',
        fontSize: '14px',
        fontWeight: 600,
        color: '#374151'
      }}>
        Evidence ({evidence.length} sources)
      </h3>
      
      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '13px'
        }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
              <th style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Claim</th>
              <th style={{ padding: '8px', textAlign: 'left', fontWeight: 600 }}>Source</th>
              <th style={{ padding: '8px', textAlign: 'center', fontWeight: 600 }}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {evidence.map((item, idx) => (
              <tr key={idx} style={{
                borderBottom: '1px solid #f3f4f6',
                backgroundColor: idx % 2 === 0 ? '#ffffff' : '#f9fafb'
              }}>
                <td style={{ padding: '8px', maxWidth: '300px' }}>
                  {item.claim.substring(0, 100)}
                  {item.claim.length > 100 ? '...' : ''}
                </td>
                <td style={{ padding: '8px', color: '#6b7280' }}>
                  {item.source}
                </td>
                <td style={{ padding: '8px', textAlign: 'center' }}>
                  <span style={{
                    padding: '2px 8px',
                    borderRadius: '4px',
                    backgroundColor: item.confidence > 0.7 ? '#d1fae5' : '#fed7aa',
                    color: item.confidence > 0.7 ? '#065f46' : '#92400e',
                    fontSize: '12px',
                    fontWeight: 500
                  }}>
                    {(item.confidence * 100).toFixed(0)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default EvidenceTable;
