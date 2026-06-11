export async function getStats() {
  const resp = await fetch("/api/stats");
  if (!resp.ok) throw new Error(`stats: ${resp.status}`);
  return resp.json();
}

export async function getReviews() {
  const resp = await fetch("/api/reviews");
  if (!resp.ok) throw new Error(`reviews: ${resp.status}`);
  return resp.json();
}

export async function getFindings(reviewId) {
  const resp = await fetch(`/api/reviews/${reviewId}/findings`);
  if (!resp.ok) throw new Error(`findings: ${resp.status}`);
  return resp.json();
}

export async function getFixActions(reviewId) {
  const resp = await fetch(`/api/reviews/${reviewId}/fix-actions`);
  if (!resp.ok) throw new Error(`fix-actions: ${resp.status}`);
  return resp.json();
}

export async function getFixAction(fixActionId) {
  const resp = await fetch(`/api/fix-actions/${fixActionId}`);
  if (!resp.ok) throw new Error(`fix-action: ${resp.status}`);
  return resp.json();
}

// Triggers a fix and returns { fix_action_id, status, finding_ids }.
// Throws an Error with the API detail message on non-202 responses.
export async function triggerFix(reviewId, body) {
  const resp = await fetch(`/api/reviews/${reviewId}/fix`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (resp.status !== 202) {
    const err = await resp.json().catch(() => ({}));
    throw new Error(err.detail || `fix: ${resp.status}`);
  }
  return resp.json();
}
