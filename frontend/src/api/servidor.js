// In production (Vercel), VITE_API_URL points to the Railway backend. 
// In local dev, it falls back to the Vite proxy path.
export const API_BASE = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api/v1`
  : '/api/v1';

// --- Static Data (Cached on client) ---
let facilityCache = null;
let graphCache = null;

export async function getFacility() {
  if (facilityCache) return facilityCache;
  const res = await fetch(`${API_BASE}/facility`);
  if (!res.ok) throw new Error('Failed to fetch facility data');
  facilityCache = await res.json();
  return facilityCache;
}

export async function getDependencyGraph() {
  if (graphCache) return graphCache;
  const res = await fetch(`${API_BASE}/dependency-graph`);
  if (!res.ok) throw new Error('Failed to fetch dependency graph');
  graphCache = await res.json();
  return graphCache;
}

// --- Dynamic Data ---

export async function getStatus() {
  const res = await fetch(`${API_BASE}/status`);
  if (!res.ok) throw new Error('Failed to fetch status');
  return res.json();
}

export async function simulateFailure(service, failure_type, severity) {
  const res = await fetch(`${API_BASE}/simulate/failure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ service, failure_type, severity })
  });
  if (!res.ok) throw new Error('Failed to simulate failure');
  return res.json();
}

export async function getIncident(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}`);
  if (!res.ok) throw new Error('Failed to fetch incident');
  return res.json();
}

export async function listIncidents() {
  const res = await fetch(`${API_BASE}/incidents`);
  if (!res.ok) throw new Error('Failed to list incidents');
  return res.json();
}

// --- Actions ---

export async function approveStep(incidentId, stepOrder) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/approve/${stepOrder}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to approve step');
  return res.json();
}

export async function rejectStep(incidentId, stepOrder) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/reject/${stepOrder}`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to reject step');
  return res.json();
}

export async function resetIncident(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/reset`, {
    method: 'POST'
  });
  if (!res.ok) throw new Error('Failed to reset incident');
  return res.json();
}

export async function validateAction(action, target_service) {
  const res = await fetch(`${API_BASE}/actions/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, target_service })
  });
  if (!res.ok) throw new Error('Failed to validate action');
  return res.json();
}

// --- Features (4, 6, 7) ---

export async function getBriefings(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/briefings`);
  if (!res.ok) throw new Error('Briefings not found');
  return res.json();
}

export async function getNotifications(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/notifications`);
  if (!res.ok) throw new Error('Notifications not found');
  return res.json();
}

export async function getComplianceReport(incidentId) {
  const res = await fetch(`${API_BASE}/incidents/${incidentId}/compliance`);
  if (!res.ok) throw new Error('Compliance report not found');
  return res.json();
}

export async function listComplianceReports() {
  const res = await fetch(`${API_BASE}/compliance-reports`);
  if (!res.ok) throw new Error('Failed to list compliance reports');
  return res.json();
}

// --- Safety Gate ---

export async function getSafetyValidations() {
  const res = await fetch(`${API_BASE}/safety-validations`);
  if (!res.ok) throw new Error('Failed to fetch safety validations');
  return res.json();
}

// --- Config & Stats ---

export async function getConfigStatus() {
  const res = await fetch(`${API_BASE}/config/status`);
  if (!res.ok) throw new Error('Failed to fetch config status');
  return res.json();
}

export async function getStats() {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to fetch stats');
  return res.json();
}

// --- SSE Streaming ---
let reasoningSource = null;

export function subscribeToReasoning(onMessage, onOpen, onError) {
  if (reasoningSource) {
    reasoningSource.close();
  }
  
  reasoningSource = new EventSource(`${API_BASE}/stream/reasoning`);
  
  reasoningSource.onopen = (e) => {
    if (onOpen) onOpen(e);
  };
  
  reasoningSource.addEventListener('reasoning', (e) => {
    if (onMessage) onMessage(e.data);
  });
  
  reasoningSource.onerror = (e) => {
    if (onError) onError(e);
  };
  
  return () => {
    if (reasoningSource) {
      reasoningSource.close();
      reasoningSource = null;
    }
  };
}
