import React, { useState } from 'react';

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  .ev-table-wrap * { box-sizing: border-box; }

  .ev-row {
    transition: background 0.18s ease;
    animation: ev-fade-in 0.3s ease both;
  }
  .ev-row:hover { background: rgba(99,102,241,0.06) !important; }

  @keyframes ev-fade-in {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .conf-bar-inner {
    transition: width 0.7s cubic-bezier(.4,0,.2,1);
  }

  .ev-source-link {
    color: #818cf8;
    text-decoration: none;
    transition: color 0.15s;
  }
  .ev-source-link:hover { color: #a5b4fc; text-decoration: underline; }
`;

const typeColors = {
  web:      { bg: 'rgba(99,102,241,0.15)', text: '#a5b4fc', border: 'rgba(99,102,241,0.3)' },
  document: { bg: 'rgba(16,185,129,0.12)', text: '#6ee7b7', border: 'rgba(16,185,129,0.25)' },
  memory:   { bg: 'rgba(245,158,11,0.12)', text: '#fcd34d', border: 'rgba(245,158,11,0.25)' },
};

const getTypeStyle = (type = 'web') => typeColors[type] || typeColors.web;

const ConfidenceBar = ({ value }) => {
  const pct = Math.min(100, Math.max(0, value * 100));
  const color = pct > 80 ? '#34d399' : pct > 60 ? '#fbbf24' : '#f87171';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <div style={{
        flex: 1, height: '5px', borderRadius: '9999px',
        background: 'rgba(255,255,255,0.08)', overflow: 'hidden', minWidth: '60px'
      }}>
        <div className="conf-bar-inner" style={{
          width: `${pct}%`, height: '100%', background: color, borderRadius: '9999px'
        }} />
      </div>
      <span style={{ fontSize: '11px', fontWeight: 700, color, minWidth: '32px', textAlign: 'right' }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
};

const EvidenceTable = ({ evidence = [] }) => {
  const [expanded, setExpanded] = useState(null);

  if (!evidence || evidence.length === 0) return null;

  const avgConf = evidence.reduce((s, e) => s + (e.confidence ?? 0.9), 0) / evidence.length;

  return (
    <div className="ev-table-wrap" style={{
      background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,27,75,0.95) 100%)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(99,102,241,0.25)',
      borderRadius: '16px',
      padding: '20px',
      margin: '12px 0',
      fontFamily: "'Inter', system-ui, sans-serif",
      boxShadow: '0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)'
    }}>
      <style>{styles}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px', borderRadius: '8px',
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '14px'
          }}>⚖️</div>
          <span style={{ fontSize: '15px', fontWeight: 700, color: '#e2e8f0', letterSpacing: '-0.02em' }}>
            Verified Evidence
          </span>
        </div>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <span style={{
            padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 600,
            background: 'rgba(99,102,241,0.18)', color: '#a5b4fc', border: '1px solid rgba(99,102,241,0.3)'
          }}>
            {evidence.length} sources
          </span>
          <span style={{
            padding: '3px 10px', borderRadius: '9999px', fontSize: '11px', fontWeight: 600,
            background: avgConf > 0.8 ? 'rgba(16,185,129,0.12)' : 'rgba(245,158,11,0.12)',
            color: avgConf > 0.8 ? '#6ee7b7' : '#fcd34d',
            border: `1px solid ${avgConf > 0.8 ? 'rgba(16,185,129,0.25)' : 'rgba(245,158,11,0.25)'}`
          }}>
            avg {(avgConf * 100).toFixed(0)}% conf
          </span>
        </div>
      </div>

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
              {['Claimed Fact', 'Source', 'Type', 'Confidence'].map(h => (
                <th key={h} style={{
                  padding: '10px 12px', textAlign: 'left',
                  fontSize: '10px', fontWeight: 700, letterSpacing: '0.08em',
                  color: '#64748b', textTransform: 'uppercase'
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {evidence.map((item, idx) => {
              const ts = getTypeStyle(item.type);
              const isOpen = expanded === idx;
              return (
                <React.Fragment key={idx}>
                  <tr
                    className="ev-row"
                    onClick={() => setExpanded(isOpen ? null : idx)}
                    style={{
                      borderBottom: '1px solid rgba(255,255,255,0.04)',
                      cursor: 'pointer',
                      animationDelay: `${idx * 0.04}s`
                    }}
                  >
                    <td style={{ padding: '12px', color: '#cbd5e1', fontWeight: 500, maxWidth: '260px' }}>
                      {item.claim}
                    </td>
                    <td style={{ padding: '12px' }}>
                      <a
                        className="ev-source-link"
                        href={item.url || '#'}
                        target="_blank"
                        rel="noreferrer"
                        onClick={e => e.stopPropagation()}
                      >
                        {item.source || 'Unknown'}
                      </a>
                    </td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        padding: '2px 8px', borderRadius: '6px', fontSize: '10px', fontWeight: 700,
                        background: ts.bg, color: ts.text, border: `1px solid ${ts.border}`,
                        textTransform: 'uppercase', letterSpacing: '0.05em'
                      }}>
                        {item.type || 'web'}
                      </span>
                    </td>
                    <td style={{ padding: '12px', minWidth: '120px' }}>
                      <ConfidenceBar value={item.confidence ?? 0.9} />
                    </td>
                  </tr>
                  {isOpen && item.excerpt && (
                    <tr style={{ background: 'rgba(99,102,241,0.05)' }}>
                      <td colSpan={4} style={{
                        padding: '12px 16px',
                        color: '#94a3b8', fontSize: '12px', fontStyle: 'italic',
                        borderBottom: '1px solid rgba(255,255,255,0.04)',
                        lineHeight: '1.6'
                      }}>
                        <strong style={{ color: '#a5b4fc', fontStyle: 'normal' }}>Excerpt: </strong>
                        {item.excerpt}
                      </td>
                    </tr>
                  )}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default EvidenceTable;
