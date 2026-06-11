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
