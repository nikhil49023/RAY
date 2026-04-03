import React from 'react';

const MemoryBadge = ({ rules = [] }) => {
  if (!rules || rules.length === 0) {
    return null;
  }
  
  return (
    <div style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '6px 12px',
      backgroundColor: '#ede9fe',
      border: '1px solid #c4b5fd',
      borderRadius: '6px',
      margin: '4px 0',
      fontSize: '12px'
    }}>
      <span style={{
        marginRight: '6px',
        fontSize: '14px'
      }}>
        🧠
      </span>
      <span style={{
        color: '#5b21b6',
        fontWeight: 500
      }}>
        {rules.length} preference{rules.length !== 1 ? 's' : ''} applied
      </span>
    </div>
  );
};

export default MemoryBadge;
