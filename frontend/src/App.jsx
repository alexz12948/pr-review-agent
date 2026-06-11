import { useCallback, useEffect, useState } from "react";
import { getReviews, getStats } from "./api.js";
import StatCards from "./components/StatCards.jsx";
import FixStatCards from "./components/FixStatCards.jsx";
import SeverityChart from "./components/SeverityChart.jsx";
import ReviewsTable from "./components/ReviewsTable.jsx";
import DetailModal from "./components/DetailModal.jsx";

export default function App() {
  const [stats, setStats] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [selectedReview, setSelectedReview] = useState(null);

  const loadStats = useCallback(() => {
    getStats()
      .then(setStats)
      .catch((err) => console.error(err));
  }, []);

  const loadReviews = useCallback(() => {
    getReviews()
      .then((data) => {
        setReviews(data);
        setError(false);
      })
      .catch((err) => {
        console.error(err);
        setError(true);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadStats();
    loadReviews();
  }, [loadStats, loadReviews]);

  return (
    <>
      <h1>PR Review Agent Dashboard</h1>
      <StatCards stats={stats} />
      <FixStatCards stats={stats} />
      <SeverityChart stats={stats} />
      <h2>Recent Reviews</h2>
      <p className="hint">Click a row to view findings and trigger automated fixes.</p>
      <ReviewsTable
        reviews={reviews}
        loading={loading}
        error={error}
        onRowClick={setSelectedReview}
      />
      {selectedReview && (
        <DetailModal
          review={selectedReview}
          onClose={() => setSelectedReview(null)}
          onStatsRefresh={loadStats}
        />
      )}
    </>
  );
}
