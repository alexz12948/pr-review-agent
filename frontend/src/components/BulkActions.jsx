export default function BulkActions({ onFix }) {
  return (
    <div className="bulk-actions">
      <button className="btn btn-dark" onClick={() => onFix({ scope: "all" })}>
        Fix All Issues
      </button>
      <button
        className="btn btn-danger"
        onClick={() => onFix({ scope: "by_severity", severity: "critical" })}
      >
        Fix Critical Only
      </button>
      <button
        className="btn btn-danger"
        onClick={() => onFix({ scope: "by_severity", severity: "high" })}
      >
        Fix High Only
      </button>
      <button
        className="btn btn-primary"
        onClick={() => onFix({ scope: "by_agent", agent_type: "security" })}
      >
        Fix Security Issues
      </button>
      <button
        className="btn btn-primary"
        onClick={() => onFix({ scope: "by_agent", agent_type: "quality" })}
      >
        Fix Quality Issues
      </button>
    </div>
  );
}
