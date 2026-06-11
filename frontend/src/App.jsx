import { useEffect, useState } from "react";
import { getReviews, getStats } from "./api.js";
import StatCards from "./components/StatCards.jsx";
import SeverityChart from "./components/SeverityChart.jsx";
import ReviewsTable from "./components/ReviewsTable.jsx";

export default function App() {
  const [stats, setStats] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    getStats().then(setStats).catch((err) => console.error(err));
    getReviews()
      .then((data) => setReviews(data))
      .catch((err) => {
        console.error(err);
        setError(true);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <h1>PR Review Agent Dashboard</h1>
      <StatCards stats={stats} />
      <SeverityChart stats={stats} />
      <h2>Recent Reviews</h2>
      <ReviewsTable reviews={reviews} loading={loading} error={error} />
    </>
  );
}
