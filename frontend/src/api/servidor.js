import * as mockData from './mockData';

// In production (Vercel), VITE_API_URL points to the Railway backend. 
// In local dev, it falls back to the Vite proxy path.
export const API_BASE = import.meta.env.VITE_API_URL 
  ? `${import.meta.env.VITE_API_URL.replace(/\/$/, '')}/api/v1`
  : '/api/v1';

// Mock fallback is on in local dev, off in production builds so the live demo only
// ever shows real backend data. Set VITE_ENABLE_MOCK_FALLBACK=true to force it on.
const MOCK_FALLBACK_ENABLED = import.meta.env.VITE_ENABLE_MOCK_FALLBACK
  ? import.meta.env.VITE_ENABLE_MOCK_FALLBACK === 'true'
  : import.meta.env.DEV;

/**
 * Helper to fetch data and automatically fall back to mock data
 * if the backend is unreachable or returns an error.
 * This ensures the portfolio showcase always looks fully populated!
 */
async function fetchWithMockFallback(url, options = {}, mockFallback) {
  if (!MOCK_FALLBACK_ENABLED) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }
  try {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    
    // If it's a list endpoint and it returned an empty array, 
    // fall back to mock data so the dashboard isn't empty.
    if (Array.isArray(data) && data.length === 0 && Array.isArray(mockFallback)) {
      console.warn(`[Demo Mode] Empty data from ${url}, using mock data.`);
      return mockFallback;
    }
    
    // Same for nested lists (e.g. stats, reports)
    if (data && typeof data === 'object') {
      if ((data.count === 0 || data.total_incidents === 0) && mockFallback) {
        console.warn(`[Demo Mode] Empty data from ${url}, using mock data.`);
        return mockFallback;
      }
    }
    
    return data;
  } catch (err) {
    console.warn(`[Demo Mode Fallback] Backend unreachable for ${url}, using mock data. Error: ${err.message}`);
    if (mockFallback !== undefined) return mockFallback;
    throw err;
  }
}

// --- Static Data (Cached on client) ---
let facilityCache = null;
let graphCache = null;

export async function getFacility() {
  if (facilityCache) return facilityCache;
  facilityCache = await fetchWithMockFallback(`${API_BASE}/facility`, {}, mockData.mockFacility);
  return facilityCache;
}

export async function getDependencyGraph() {
  if (graphCache) return graphCache;
  graphCache = await fetchWithMockFallback(`${API_BASE}/dependency-graph`, {}, mockData.mockGraph);
  return graphCache;
}

export async function getServices() {
  return fetchWithMockFallback(`${API_BASE}/services`, {}, {});
}

// --- Dynamic Data ---

export async function getStatus() {
  return fetchWithMockFallback(`${API_BASE}/status`, {}, mockData.mockStatus);
}

export async function simulateFailure(service, failure_type, severity) {
  const res = await fetch(`${API_BASE}/simulate/failure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ service, failure_type, severity })
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);
  return data;
}

export async function resetChaos() {
  const res = await fetch(`${API_BASE}/chaos/reset`, { method: 'POST' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function getIncident(incidentId) {
  const mockInc = mockData.mockIncidents.find(i => i.incident_id === incidentId) || mockData.mockIncidents[0];
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}`, {}, mockInc);
}

export async function listIncidents() {
  return fetchWithMockFallback(`${API_BASE}/incidents`, {}, mockData.mockIncidents);
}

// --- Actions ---

export async function approveStep(incidentId, stepOrder) {
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}/approve/${stepOrder}`, { method: 'POST' }, { status: 'approved' });
}

export async function rejectStep(incidentId, stepOrder) {
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}/reject/${stepOrder}`, { method: 'POST' }, { status: 'rejected' });
}

export async function resetIncident(incidentId) {
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}/reset`, { method: 'POST' }, { status: 'reset' });
}

export async function validateAction(action, target_service) {
  return fetchWithMockFallback(`${API_BASE}/actions/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ action, target_service })
  }, { allowed: false, refusal: { reason: "Mock mode block active" } });
}

// --- Features (4, 6, 7) ---

export async function getBriefings(incidentId) {
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}/briefings`, {}, {
    incident_id: incidentId,
    engineer: "Mock engineer briefing",
    physician: "Mock physician briefing",
    administrator: "Mock admin briefing"
  });
}

export async function getNotifications(incidentId) {
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}/notifications`, {}, { notifications: [], count: 0 });
}

export async function getComplianceReport(incidentId) {
  const report = mockData.mockComplianceReports.reports.find(r => r.incident_id === incidentId) || mockData.mockComplianceReports.reports[0];
  return fetchWithMockFallback(`${API_BASE}/incidents/${incidentId}/compliance`, {}, report);
}

export async function listComplianceReports() {
  return fetchWithMockFallback(`${API_BASE}/compliance-reports`, {}, mockData.mockComplianceReports);
}

// --- Safety Gate ---

export async function getSafetyValidations() {
  return fetchWithMockFallback(`${API_BASE}/safety-validations`, {}, mockData.mockValidations);
}

// --- Config & Stats ---

export async function getConfigStatus() {
  return fetchWithMockFallback(`${API_BASE}/config/status`, {}, mockData.mockConfig);
}

export async function getStats() {
  return fetchWithMockFallback(`${API_BASE}/stats`, {}, mockData.mockStats);
}

// --- SSE Streaming ---
let reasoningSource = null;

export function subscribeToReasoning(onMessage, onOpen, onError) {
  if (reasoningSource) {
    reasoningSource.close();
  }
  
  try {
    reasoningSource = new EventSource(`${API_BASE}/stream/reasoning`);
    
    reasoningSource.onopen = (e) => {
      if (onOpen) onOpen(e);
    };
    
    reasoningSource.addEventListener('reasoning', (e) => {
      if (onMessage) onMessage(e.data);
    });
    
    reasoningSource.onerror = (e) => {
      // In a mock scenario, SSE will fail if backend is down. We just silently ignore or trigger error.
      if (onError) onError(e);
    };
  } catch (err) {
    if (onError) onError(err);
  }
  
  return () => {
    if (reasoningSource) {
      reasoningSource.close();
      reasoningSource = null;
    }
  };
}
