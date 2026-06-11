function SeverityCategoryBadge({ finding }) {
  if (finding.severity) {
    return <span className={`badge sev-${finding.severity}`}>{finding.severity}</span>;
  }
  if (finding.category) {
    return <span className="badge cat-badge">{finding.category}</span>;
  }
  return null;
}

function FixStatus({ status }) {
  switch (status) {
    case "fixed":
      return <span className="status-fixed">✔ Fixed</span>;
    case "failed":
      return <span className="status-failed">✘ Failed</span>;
    case "in_progress":
      return (
        <span className="status-in_progress">
          <span className="spinner" />
          Fixing…
        </span>
      );
    case "skipped":
      return <span className="status-pending">Skipped</span>;
    default:
      return <span className="status-pending">Pending</span>;
  }
}

export default function FindingItem({ finding, onFix }) {
  const loc = [finding.file, finding.line != null ? `:${finding.line}` : ""]
    .join("")
    .trim();
  return (
    <div className="finding" id={`finding-${finding.id}`}>
      <div className="finding-top">
        <div>
          <div className="finding-meta">
            <span className={`badge agent-${finding.agent_type}`}>{finding.agent_type}</span>
            <SeverityCategoryBadge finding={finding} />
          </div>
          <div className="finding-title">{finding.title}</div>
          <div className="finding-desc">{finding.description}</div>
          {loc && <div className="finding-loc">{loc}</div>}
          <div className="finding-status">
            <FixStatus status={finding.fix_status} />
          </div>
        </div>
        <div className="finding-actions">
          {finding.fix_status === "pending" && (
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onFix({ scope: "single", finding_id: finding.id })}
            >
              Fix This
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
