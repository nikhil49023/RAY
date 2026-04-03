import React, { useState } from 'react';

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  .mb-wrap * { box-sizing: border-box; }

  @keyframes mb-badge-in {
    from { opacity: 0; transform: scale(0.85); }
    to   { opacity: 1; transform: scale(1); }
  }

  @keyframes mb-expand {
    from { opacity: 0; max-height: 0; }
    to   { opacity: 1; max-height: 400px; }
  }

  .mb-badge {
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    animation: mb-badge-in 0.2s ease both;
  }
  .mb-badge:hover { transform: translateY(-1px); }

  .mb-expanded {
    animation: mb-expand 0.3s ease both;
    overflow: hidden;
  }
`;

/* Map priority keywords → visual tier */
const getTier = (rule = '') => {
  const r = rule.toLowerCase();
  if (r.includes('always') || r.includes('never') || r.includes('must')) {
    return { label: 'HIGH',   bg: 'rgba(239,68,68,0.15)',   text: '#fca5a5', border: 'rgba(239,68,68,0.3)',   dot: '#ef4444' };
  }
  if (r.includes('prefer') || r.includes('cite') || r.includes('avoid')) {
    return { label: 'MED',    bg: 'rgba(245,158,11,0.15)',  text: '#fcd34d', border: 'rgba(245,158,11,0.3)',  dot: '#f59e0b' };
  }
  return   { label: 'LOW',    bg: 'rgba(99,102,241,0.12)',  text: '#a5b4fc', border: 'rgba(99,102,241,0.25)', dot: '#6366f1' };
};

const MemoryBadge = ({ rules = [] }) => {
  const [open, setOpen] = useState(false);

  if (!rules || rules.length === 0) return null;

  const highCount = rules.filter(r => getTier(r).label === 'HIGH').length;
  const medCount  = rules.filter(r => getTier(r).label === 'MED').length;

  return (
    <div className="mb-wrap" style={{
      background: 'linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,27,75,0.95) 100%)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(99,102,241,0.2)',
      borderRadius: '12px',
      margin: '8px 0',
      fontFamily: "'Inter', system-ui, sans-serif",
      boxShadow: '0 4px 20px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)',
      overflow: 'hidden'
    }}>
      <style>{styles}</style>

      {/* Summary row — click to toggle */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center',
          gap: '10px', padding: '10px 14px', background: 'none',
          border: 'none', cursor: 'pointer', textAlign: 'left'
        }}
      >
        <div style={{
          width: '26px', height: '26px', borderRadius: '7px',
          background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '13px', flexShrink: 0
        }}>🧠</div>

        <span style={{ fontSize: '13px', fontWeight: 600, color: '#e2e8f0', flex: 1 }}>
          {rules.length} Behavioral Rule{rules.length !== 1 ? 's' : ''} Applied
        </span>

        {/* Tier summary pills */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {highCount > 0 && (
            <span style={{
              padding: '1px 7px', borderRadius: '9999px', fontSize: '10px', fontWeight: 700,
              background: 'rgba(239,68,68,0.15)', color: '#fca5a5', border: '1px solid rgba(239,68,68,0.3)'
            }}>
              {highCount} HIGH
            </span>
          )}
          {medCount > 0 && (
            <span style={{
              padding: '1px 7px', borderRadius: '9999px', fontSize: '10px', fontWeight: 700,
              background: 'rgba(245,158,11,0.15)', color: '#fcd34d', border: '1px solid rgba(245,158,11,0.3)'
            }}>
              {medCount} MED
            </span>
          )}
        </div>

        <span style={{ fontSize: '12px', color: '#475569', transition: 'transform 0.2s', transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}>
          ▾
        </span>
      </button>

      {/* Expanded badge list */}
      {open && (
        <div className="mb-expanded" style={{
          padding: '4px 14px 14px',
          display: 'flex', flexDirection: 'column', gap: '6px'
        }}>
          {rules.map((rule, idx) => {
            const t = getTier(rule);
            return (
              <div className="mb-badge" key={idx} style={{
                display: 'flex', alignItems: 'flex-start', gap: '8px',
                padding: '8px 10px', borderRadius: '8px',
                background: t.bg, border: `1px solid ${t.border}`,
                animationDelay: `${idx * 0.04}s`
              }}>
                <div style={{
                  width: '6px', height: '6px', borderRadius: '50%',
                  background: t.dot, marginTop: '5px', flexShrink: 0
                }} />
                <div style={{ flex: 1 }}>
                  <span style={{
                    fontSize: '10px', fontWeight: 700, color: t.text, marginRight: '6px',
                    textTransform: 'uppercase', letterSpacing: '0.06em'
                  }}>
                    [{t.label}]
                  </span>
                  <span style={{ fontSize: '12px', color: '#94a3b8', lineHeight: '1.5' }}>
                    {rule}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default MemoryBadge;
