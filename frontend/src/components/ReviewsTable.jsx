export default function ReviewsTable({ reviews, loading, error, onRowClick }) {
  let body;
  if (loading) {
    body = (
      <tr>
        <td colSpan={7} className="loading">Loading…</td>
      </tr>
    );
  } else if (error) {
    body = (
      <tr>
        <td colSpan={7} className="loading">Error loading reviews.</td>
      </tr>
    );
  } else if (!reviews.length) {
    body = (
      <tr>
        <td colSpan={7} className="loading">No reviews yet.</td>
      </tr>
    );
  } else {
    body = reviews.map((r) => {
      const prUrl = `https://github.com/${r.repo}/pull/${r.pr_number}`;
      const date = new Date(r.created_at).toLocaleDateString();
      return (
        <tr key={r.id} onClick={() => onRowClick && onRowClick(r)}>
          <td>{r.repo}</td>
          <td>
            <a
              href={prUrl}
              target="_blank"
              rel="noreferrer"
              onClick={(e) => e.stopPropagation()}
            >
              #{r.pr_number}
            </a>
          </td>
          <td className={`status-${r.status}`}>{r.status}</td>
          <td>{r.security_findings}</td>
          <td>{r.quality_findings}</td>
          <td>{r.latency_seconds.toFixed(1)}s</td>
          <td>{date}</td>
        </tr>
      );
    });
  }

  return (
    <table>
      <thead>
        <tr>
          <th>Repo</th>
          <th>PR</th>
          <th>Status</th>
          <th>Security</th>
          <th>Quality</th>
          <th>Latency</th>
          <th>Date</th>
        </tr>
      </thead>
      <tbody id="reviews-body">{body}</tbody>
    </table>
  );
}
