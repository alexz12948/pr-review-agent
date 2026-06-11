export default function FixStatCards({ stats }) {
  const fs = stats ? stats.fix_stats : null;
  const totalFixes = fs ? fs.total_fix_actions : "—";
  const successRate = fs ? `${Math.round(fs.fix_success_rate * 100)}%` : "—";
  const avgLatency = fs ? `${fs.avg_fix_latency}s` : "—";
  return (
    <div className="cards">
      <div className="card">
        <h3>Total Fixes Attempted</h3>
        <div className="value" id="total-fixes">{totalFixes}</div>
      </div>
      <div className="card">
        <h3>Fix Success Rate</h3>
        <div className="value" id="fix-success-rate">{successRate}</div>
      </div>
      <div className="card">
        <h3>Avg Fix Latency</h3>
        <div className="value" id="avg-fix-latency">{avgLatency}</div>
      </div>
    </div>
  );
}
