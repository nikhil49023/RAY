import React from 'react';

const styles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

  .dp-wrap * { box-sizing: border-box; }

  @keyframes dp-bar-grow {
    from { transform: scaleX(0); }
    to   { transform: scaleX(1); }
  }

  @keyframes dp-count-up {
    from { opacity: 0; transform: translateY(6px); }
    to   { opacity: 1; transform: translateY(0); }
  }

  .dp-metric-card {
    transition: transform 0.18s ease, box-shadow 0.18s ease;
    animation: dp-count-up 0.35s ease both;
  }
  .dp-metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 24px rgba(0,0,0,0.4) !important;
  }

  .dp-bar-fill {
    transform-origin: left;
    animation: dp-bar-grow 0.7s cubic-bezier(.4,0,.2,1) both;
  }
`;

/* Thin SVG ring for a single metric */
const Ring = ({ value, max, color, size = 52, stroke = 5 }) => {
  const r = (size - stroke) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(1, value / max);
  const dash = pct * circ;
  return (
    <svg width={size} height={size} style={{ transform: 'rotate(-90deg)' }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={stroke} />
      <circle
        cx={size/2} cy={size/2} r={r} fill="none"
        stroke={color} strokeWidth={stroke}
        strokeDasharray={`${dash} ${circ}`}
        strokeLinecap="round"
        style={{ transition: 'stroke-dasharray 0.7s cubic-bezier(.4,0,.2,1)' }}
      />
    </svg>
  );
};

const MetricCard = ({ label, value, icon, ringMax, ringColor = '#818cf8', delay = 0, sub = null }) => (
  <div className="dp-metric-card" style={{
    background: 'rgba(255,255,255,0.04)',
    border: '1px solid rgba(255,255,255,0.07)',
    borderRadius: '12px',
    padding: '14px 16px',
    flex: '1 1 120px',
    minWidth: '120px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.25)',
    animationDelay: `${delay}s`
  }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div>
        <div style={{ fontSize: '10px', fontWeight: 700, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          {icon} {label}
        </div>
        <div style={{ fontSize: '22px', fontWeight: 800, color: '#e2e8f0', marginTop: '4px', letterSpacing: '-0.03em' }}>
          {value}
        </div>
        {sub && <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>{sub}</div>}
      </div>
      {ringMax != null && (
        <div style={{ position: 'relative' }}>
          <Ring value={typeof value === 'string' ? parseFloat(value) : value} max={ringMax} color={ringColor} />
        </div>
      )}
    </div>
  </div>
);

const DashboardPanel = ({ metrics = {} }) => {
  const {
    confidence       = 0.95,
    sourceCount      = 0,
    tokenUsage       = 0,
    processingTime   = 0,
    factualCertainty = 0.98,
    tokenBudget      = 12000,   // max context budget
    summaryTurn      = null,    // which turn last summary ran
  } = metrics;

  const tokenPct       = Math.min(1, tokenUsage / tokenBudget);
  const tokenBarColor  = tokenPct > 0.85 ? '#f87171' : tokenPct > 0.6 ? '#fbbf24' : '#34d399';
  const tokenBudgetPct = (tokenPct * 100).toFixed(0);

  return (
    <div className="dp-wrap" style={{
      background: 'linear-gradient(135deg, rgba(15,23,42,0.97) 0%, rgba(17,24,39,0.97) 100%)',
      backdropFilter: 'blur(16px)',
      border: '1px solid rgba(99,102,241,0.18)',
      borderRadius: '16px',
      padding: '20px',
      marginBottom: '16px',
      fontFamily: "'Inter', system-ui, sans-serif",
      boxShadow: '0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04)'
    }}>
      <style>{styles}</style>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px', borderRadius: '8px',
            background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '13px'
          }}>📊</div>
          <span style={{ fontSize: '15px', fontWeight: 700, color: '#e2e8f0', letterSpacing: '-0.02em' }}>
            Session Telemetry
          </span>
        </div>
        {summaryTurn != null && (
          <span style={{
            fontSize: '10px', padding: '2px 8px', borderRadius: '6px',
            background: 'rgba(245,158,11,0.12)', color: '#fcd34d',
            border: '1px solid rgba(245,158,11,0.25)', fontWeight: 600
          }}>
            📝 summarized @ turn {summaryTurn}
          </span>
        )}
      </div>

      {/* Metric Cards */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '16px' }}>
        <MetricCard
          label="Confidence"
          value={`${(confidence * 100).toFixed(1)}%`}
          icon="🎯"
          ringMax={100}
          ringColor="#34d399"
          delay={0}
          sub="overall"
        />
        <MetricCard
          label="Sources"
          value={sourceCount}
          icon="📚"
          ringMax={20}
          ringColor="#818cf8"
          delay={0.05}
          sub="retrieved"
        />
        <MetricCard
          label="Tokens"
          value={tokenUsage.toLocaleString()}
          icon="🪙"
          ringMax={tokenBudget}
          ringColor={tokenBarColor}
          delay={0.10}
          sub={`of ${tokenBudget.toLocaleString()} budget`}
        />
        <MetricCard
          label="Latency"
          value={`${processingTime.toFixed(2)}s`}
          icon="⚡"
          ringMax={30}
          ringColor="#fbbf24"
          delay={0.15}
          sub="wall clock"
        />
      </div>

      {/* Context Budget Bar */}
      <div style={{
        background: 'rgba(255,255,255,0.03)', borderRadius: '10px',
        padding: '12px 14px', border: '1px solid rgba(255,255,255,0.06)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', alignItems: 'center' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>
            Context Budget
          </span>
          <span style={{ fontSize: '11px', fontWeight: 700, color: tokenBarColor }}>
            {tokenBudgetPct}% used
          </span>
        </div>
        <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow:'hidden' }}>
          <div className="dp-bar-fill" style={{
            height: '100%', width: `${tokenBudgetPct}%`,
            background: `linear-gradient(90deg, ${tokenBarColor}, ${tokenBarColor}cc)`,
            borderRadius: '3px'
          }} />
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '6px' }}>
          <span style={{ fontSize: '9px', color: '#334155' }}>0</span>
          <span style={{ fontSize: '9px', color: '#334155' }}>8k warn</span>
          <span style={{ fontSize: '9px', color: '#334155' }}>{(tokenBudget/1000).toFixed(0)}k limit</span>
        </div>
      </div>

      {/* Factual Grounding */}
      <div style={{
        marginTop: '10px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px',
        padding: '12px 14px', border: '1px solid rgba(255,255,255,0.06)'
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#64748b' }}>Factual Grounding</span>
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#34d399' }}>
            {(factualCertainty * 100).toFixed(1)}%
          </span>
        </div>
        <div style={{ height: '6px', background: 'rgba(255,255,255,0.06)', borderRadius: '3px', overflow:'hidden' }}>
          <div className="dp-bar-fill" style={{
            height: '100%', width: `${factualCertainty * 100}%`,
            background: 'linear-gradient(90deg, #10b981, #34d399)',
            borderRadius: '3px'
          }} />
        </div>
      </div>
    </div>
  );
};

export default DashboardPanel;
