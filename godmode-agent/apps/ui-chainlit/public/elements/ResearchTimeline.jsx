import React, { useEffect, useState } from 'react';

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  .rt-wrap * { box-sizing: border-box; }

  @keyframes rt-pulse-ring {
    0%   { box-shadow: 0 0 0 0 rgba(99,102,241,0.7); }
    70%  { box-shadow: 0 0 0 8px rgba(99,102,241,0); }
    100% { box-shadow: 0 0 0 0 rgba(99,102,241,0); }
  }

  @keyframes rt-spin {
    to { transform: rotate(360deg); }
  }

  @keyframes rt-slide-in {
    from { opacity: 0; transform: translateX(-10px); }
    to   { opacity: 1; transform: translateX(0); }
  }

  @keyframes rt-fill-bar {
    from { transform: scaleX(0); }
    to   { transform: scaleX(1); }
  }

  .rt-node-active-dot {
    animation: rt-pulse-ring 1.4s cubic-bezier(0.455, 0.030, 0.515, 0.955) infinite;
  }

  .rt-spinner {
    width: 10px; height: 10px; border-radius: 50%;
    border: 2px solid rgba(99,102,241,0.3);
    border-top-color: #818cf8;
    animation: rt-spin 0.8s linear infinite;
  }

  .rt-item {
    animation: rt-slide-in 0.25s ease both;
  }

  .rt-connector-fill {
    transform-origin: top;
    animation: rt-fill-bar 0.4s ease both;
  }
`;

const NODE_STEPS = [
  { id: 'intent_router',    label: 'Intent Analysis',   icon: '🔍', desc: 'Classifying user request' },
  { id: 'memory_prefetch',  label: 'Memory Retrieval',  icon: '🧠', desc: 'Fetching behavioral rules' },
  { id: 'planner',          label: 'Dynamic Planning',  icon: '📋', desc: 'Generating subtask plan' },
  { id: 'doc_rag',          label: 'Document Search',   icon: '📄', desc: 'Querying Qdrant index' },
  { id: 'web_rag',          label: 'Web Search',        icon: '🌐', desc: 'Retrieving live sources' },
  { id: 'verifier',         label: 'Fact Verification', icon: '⚖️', desc: 'Cross-checking claims' },
  { id: 'composer',         label: 'Final Composition', icon: '✍️', desc: 'Generating response' },
  { id: 'memory_writeback', label: 'Memory Storage',    icon: '💾', desc: 'Persisting preferences' },
];

const statusConfig = {
  pending:   { label: 'PENDING',   bg: 'rgba(245,158,11,0.15)', color: '#fcd34d', border: 'rgba(245,158,11,0.3)' },
  running:   { label: 'RUNNING',   bg: 'rgba(99,102,241,0.15)', color: '#a5b4fc', border: 'rgba(99,102,241,0.3)' },
  completed: { label: 'DONE',      bg: 'rgba(16,185,129,0.12)', color: '#6ee7b7', border: 'rgba(16,185,129,0.25)' },
  error:     { label: 'ERROR',     bg: 'rgba(239,68,68,0.12)',  color: '#fca5a5', border: 'rgba(239,68,68,0.25)' },
};

const ResearchTimeline = ({
  status = 'pending',
  activeNode = '',
  completedNodes = [],
  timings = {},      // { node_id: seconds_taken }
  error = null,
}) => {
  const [tick, setTick] = useState(0);
  const [activeStart, setActiveStart] = useState(Date.now());

  // Re-start elapsed timer whenever activeNode changes
  useEffect(() => {
    setActiveStart(Date.now());
    const id = setInterval(() => setTick(t => t + 1), 500);
    return () => clearInterval(id);
  }, [activeNode]);

  const elapsedSec = ((Date.now() - activeStart) / 1000).toFixed(1);
  const sc = statusConfig[status] || statusConfig.pending;

  return (
    <div className="rt-wrap" style={{
      background: 'linear-gradient(135deg, rgba(15,23,42,0.97) 0%, rgba(17,24,39,0.97) 100%)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(99,102,241,0.2)',
      borderRadius: '16px',
      padding: '20px 24px',
      marginBottom: '16px',
      fontFamily: "'Inter', system-ui, sans-serif",
      boxShadow: '0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04)'
    }}>
      <style>{styles}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px', borderRadius: '8px',
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px'
          }}>⚡</div>
          <span style={{ fontSize: '15px', fontWeight: 700, color: '#e2e8f0', letterSpacing: '-0.02em' }}>
            Research Workflow
          </span>
        </div>
        <span style={{
          padding: '3px 12px', borderRadius: '9999px', fontSize: '10px',
          fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
          background: sc.bg, color: sc.color, border: `1px solid ${sc.border}`
        }}>
          {sc.label}
        </span>
      </div>

      {/* Steps */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {NODE_STEPS.map((step, idx) => {
          const isActive    = activeNode === step.id;
          const isCompleted = completedNodes.includes(step.id);
          const isPending   = !isActive && !isCompleted;
          const timing      = timings[step.id];
          const isLast      = idx === NODE_STEPS.length - 1;

          const dotBg = isCompleted
            ? 'linear-gradient(135deg,#10b981,#059669)'
            : isActive
              ? 'linear-gradient(135deg,#6366f1,#8b5cf6)'
              : 'rgba(255,255,255,0.06)';

          return (
            <div key={step.id} className="rt-item" style={{
              display: 'flex', animationDelay: `${idx * 0.035}s`
            }}>
              {/* Left: dot + connector */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginRight: '14px' }}>
                <div
                  className={isActive ? 'rt-node-active-dot' : ''}
                  style={{
                    width: '30px', height: '30px', borderRadius: '10px',
                    background: dotBg, border: isActive ? '1px solid rgba(99,102,241,0.6)' : '1px solid rgba(255,255,255,0.08)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '14px', flexShrink: 0,
                    color: isPending ? '#475569' : 'white',
                    transition: 'background 0.3s, border 0.3s',
                  }}
                >
                  {isCompleted ? '✓' : isActive ? <div className="rt-spinner" /> : step.icon}
                </div>
                {!isLast && (
                  <div style={{ width: '2px', flex: 1, minHeight: '20px', background: 'rgba(255,255,255,0.06)', position: 'relative', overflow: 'hidden' }}>
                    {isCompleted && (
                      <div className="rt-connector-fill" style={{
                        position: 'absolute', inset: 0,
                        background: 'linear-gradient(180deg,#10b981,#059669)',
                      }} />
                    )}
                  </div>
                )}
              </div>

              {/* Right: label + desc */}
              <div style={{ paddingBottom: isLast ? 0 : '18px', flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', paddingTop: '5px' }}>
                  <span style={{
                    fontSize: '13px', fontWeight: isActive || isCompleted ? 600 : 400,
                    color: isCompleted ? '#e2e8f0' : isActive ? '#a5b4fc' : '#475569',
                    transition: 'color 0.3s'
                  }}>
                    {step.label}
                  </span>
                  {timing != null && (
                    <span style={{
                      fontSize: '10px', color: '#6ee7b7', fontWeight: 600,
                      background: 'rgba(16,185,129,0.1)', padding: '1px 6px', borderRadius: '4px'
                    }}>
                      {timing.toFixed(2)}s
                    </span>
                  )}
                  {isActive && (
                    <span style={{ fontSize: '10px', color: '#818cf8' }}>
                      {elapsedSec}s elapsed
                    </span>
                  )}
                </div>
                {(isActive || isCompleted) && (
                  <div style={{ fontSize: '11px', color: '#475569', marginTop: '2px' }}>
                    {step.desc}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Error banner */}
      {error && (
        <div style={{
          marginTop: '16px', padding: '10px 14px',
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.25)',
          borderRadius: '8px', color: '#fca5a5', fontSize: '12px', lineHeight: '1.5'
        }}>
          <strong>Error: </strong>{error}
        </div>
      )}
    </div>
  );
};

export default ResearchTimeline;
