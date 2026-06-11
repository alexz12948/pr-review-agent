export default function StatCards({ stats }) {
  const totalPrs = stats ? stats.total_prs : "—";
  const avgLatency = stats ? `${stats.avg_latency}s` : "—";
  let totalFindings = "—";
  if (stats) {
    totalFindings =
      (stats.total_security_findings || 0) +
      (stats.total_quality_findings || 0);
  }
  return (
    <div className="cards">
      <div className="card">
        <h3>Total PRs Reviewed</h3>
        <div className="value" id="total-prs">{totalPrs}</div>
      </div>
      <div className="card">
        <h3>Avg Review Latency</h3>
        <div className="value" id="avg-latency">{avgLatency}</div>
      </div>
      <div className="card">
        <h3>Total Findings</h3>
        <div className="value" id="total-findings">{totalFindings}</div>
      </div>
    </div>
  );
}
