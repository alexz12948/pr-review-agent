function fmtDuration(sec) {
  if (sec == null) return "—";
  return `${sec.toFixed(1)}s`;
}

export default function FixHistory({ actions, loading, error }) {
  if (loading) return <p className="loading">Loading fix history…</p>;
  if (error) return <p className="loading">Error loading fix history.</p>;
  if (!actions.length) return <p className="loading">No fix actions yet.</p>;

  return (
    <>
      {actions.map((a) => {
        const when = new Date(a.created_at).toLocaleString();
        const hasCommit = a.commit_sha && a.fix_pr_url;
        return (
          <div className="fix-history-item" key={a.id}>
            <div>
              <span className={`status-${a.status}`}>{a.status}</span>
              {" · scope: "}
              <strong>{a.scope}</strong>
              {` · ${a.finding_ids.length} finding(s)`}
              {` · ${fmtDuration(a.latency_seconds)}`}
              {hasCommit && (
                <>
                  {" · "}
                  <a href={a.fix_pr_url} target="_blank" rel="noreferrer">
                    {a.commit_sha.slice(0, 8)}
                  </a>
                </>
              )}
            </div>
            {a.result_summary && <div>{a.result_summary}</div>}
            <div className="meta">
              {when}
              {a.devin_session_id ? ` · session ${a.devin_session_id}` : ""}
            </div>
          </div>
        );
      })}
    </>
  );
}
