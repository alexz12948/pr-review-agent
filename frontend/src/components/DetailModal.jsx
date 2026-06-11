import { useCallback, useEffect, useRef, useState } from "react";
import {
  getFindings,
  getFixActions,
  getFixAction,
  triggerFix,
} from "../api.js";
import BulkActions from "./BulkActions.jsx";
import FindingItem from "./FindingItem.jsx";
import FixHistory from "./FixHistory.jsx";

export default function DetailModal({ review, onClose, onStatsRefresh }) {
  const [findings, setFindings] = useState([]);
  const [findingsLoading, setFindingsLoading] = useState(true);
  const [findingsError, setFindingsError] = useState(false);

  const [actions, setActions] = useState([]);
  const [actionsLoading, setActionsLoading] = useState(true);
  const [actionsError, setActionsError] = useState(false);

  // Active polling intervals keyed by fix_action_id.
  const pollers = useRef({});

  const loadFindings = useCallback(async () => {
    try {
      setFindings(await getFindings(review.id));
      setFindingsError(false);
    } catch (err) {
      console.error(err);
      setFindingsError(true);
    } finally {
      setFindingsLoading(false);
    }
  }, [review.id]);

  const loadActions = useCallback(async () => {
    try {
      setActions(await getFixActions(review.id));
      setActionsError(false);
    } catch (err) {
      console.error(err);
      setActionsError(true);
    } finally {
      setActionsLoading(false);
    }
  }, [review.id]);

  const startPolling = useCallback(
    (fixActionId) => {
      if (pollers.current[fixActionId]) return;
      pollers.current[fixActionId] = setInterval(async () => {
        try {
          const fa = await getFixAction(fixActionId);
          if (fa.status === "completed" || fa.status === "failed") {
            clearInterval(pollers.current[fixActionId]);
            delete pollers.current[fixActionId];
            await loadFindings();
            await loadActions();
            onStatsRefresh();
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 5000);
    },
    [loadFindings, loadActions, onStatsRefresh]
  );

  const onFix = useCallback(
    async (body) => {
      try {
        const data = await triggerFix(review.id, body);
        await loadFindings();
        await loadActions();
        startPolling(data.fix_action_id);
      } catch (err) {
        console.error("Failed to trigger fix:", err);
        alert(`Could not start fix: ${err.message}`);
      }
    },
    [review.id, loadFindings, loadActions, startPolling]
  );

  useEffect(() => {
    loadFindings();
    loadActions();
    const active = pollers.current;
    return () => {
      Object.values(active).forEach(clearInterval);
    };
  }, [loadFindings, loadActions]);

  const prUrl = `https://github.com/${review.repo}/pull/${review.pr_number}`;

  return (
    <div
      className="modal-overlay"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal">
        <div className="modal-header">
          <h2>
            {review.repo}{" "}
            <a href={prUrl} target="_blank" rel="noreferrer">
              #{review.pr_number}
            </a>
          </h2>
          <button className="modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="modal-body">
          <BulkActions onFix={onFix} />
          <div className="section-title">Findings</div>
          {findingsLoading ? (
            <p className="loading">Loading findings…</p>
          ) : findingsError ? (
            <p className="loading">Error loading findings.</p>
          ) : findings.length === 0 ? (
            <p className="loading">No findings recorded for this review.</p>
          ) : (
            findings.map((f) => (
              <FindingItem key={f.id} finding={f} onFix={onFix} />
            ))
          )}
          <div className="section-title">Fix History</div>
          <FixHistory
            actions={actions}
            loading={actionsLoading}
            error={actionsError}
          />
        </div>
      </div>
    </div>
  );
}
