import { Pie } from "react-chartjs-2";
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from "chart.js";

ChartJS.register(ArcElement, Tooltip, Legend);

export default function SeverityChart({ stats }) {
  const total_findings = stats
    ? stats.total_findings
    : { critical: 0, high: 0, medium: 0, low: 0 };
  const data = {
    labels: ["Critical", "High", "Medium", "Low"],
    datasets: [
      {
        data: [
          total_findings.critical,
          total_findings.high,
          total_findings.medium,
          total_findings.low,
        ],
        backgroundColor: ["#e74c3c", "#e67e22", "#f1c40f", "#3498db"],
      },
    ],
  };
  const options = {
    responsive: true,
    plugins: { legend: { position: "bottom" } },
  };
  return (
    <div className="chart-container">
      <h3 className="chart-title">Severity Breakdown</h3>
      <Pie data={data} options={options} />
    </div>
  );
}
