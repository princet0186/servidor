import React, { useState, useEffect, useRef } from 'react';
import { Heart, Pill, FlaskConical, AlertTriangle, Timer, CheckCircle2, Activity } from 'lucide-react';
import BlastRadius from '../components/BlastRadius';
import ReasoningTimeline from '../components/ReasoningTimeline';
import IncidentBriefing from '../components/IncidentBriefing';
import NotificationLog from '../components/NotificationLog';
import ComplianceReport from '../components/ComplianceReport';
import DependencyGraph from '../components/DependencyGraph';
import ServiceHealthStrip from '../components/ServiceHealthStrip';
import { 
  getStatus, simulateFailure, subscribeToReasoning, getIncident, 
  getServices, approveStep, rejectStep
} from '../api/servidor';
import './Dashboard.css';

// ── Countdown Timer Component ──
function CountdownTimer({ harmMinutes, startedAt, resolved }) {
  const [remaining, setRemaining] = useState(null);

  useEffect(() => {
    if (!harmMinutes || !startedAt) return;

    const deadline = new Date(startedAt).getTime() + (harmMinutes * 60 * 1000);

    const tick = () => {
      const now = Date.now();
      const diff = Math.max(0, Math.floor((deadline - now) / 1000));
      setRemaining(diff);
    };

    tick();
    const interval = setInterval(tick, 1000);
    return () => clearInterval(interval);
  }, [harmMinutes, startedAt]);

  if (remaining === null) return null;

  if (resolved) {
    return (
      <div className="countdown-resolved anim-slide-down">
        <div className="countdown-icon">
          <CheckCircle2 size={24} color="var(--status-safe)" />
        </div>
        <div className="countdown-info">
          <span className="countdown-label">INCIDENT RESOLVED</span>
          <span className="countdown-sublabel">All patients safe. System recovered.</span>
        </div>
        <div className="countdown-time" style={{ color: 'var(--status-safe)', fontSize: '24px' }}>
          SAFE
        </div>
      </div>
    );
  }

  const mins = Math.floor(remaining / 60);
  const secs = remaining % 60;
  const timeStr = `${mins}:${secs.toString().padStart(2, '0')}`;
  const isUrgent = remaining < 120; // less than 2 minutes

  return (
    <div className="countdown-banner anim-slide-down">
      <div className="countdown-icon">
        <Timer size={24} color="var(--status-critical)" />
      </div>
      <div className="countdown-time" style={{ fontSize: isUrgent ? '42px' : '36px' }}>
        {remaining <= 0 ? 'OVERDUE' : timeStr}
      </div>
      <div className="countdown-info">
        <span className="countdown-label">TIME TO PATIENT HARM</span>
        <span className="countdown-sublabel">
          {remaining <= 0 
            ? 'Patient safety window has expired — immediate action required'
            : `Estimated window before patient outcomes are compromised`
          }
        </span>
      </div>
    </div>
  );
}


// ── Scenario Card Component (with icons + colors) ──
function ScenarioCard({ title, icon: Icon, colorClass, patients, icu, workflows, isSimulating, onSimulate }) {
  return (
    <div className={`card scenario-card scenario-${colorClass} ${isSimulating ? 'simulating' : ''}`}>
      <div className="scenario-card-header">
        <h3 className="text-section-header">{title}</h3>
        <div className={`scenario-card-icon ${colorClass}`}>
          <Icon size={18} />
        </div>
      </div>
      
      <div>
        <div className="scenario-card-metrics">
          <span className="text-hero-metric" style={{ 
            color: isSimulating ? 'var(--status-critical)' : 'var(--on-surface)',
            fontSize: '32px'
          }}>
            {patients}
          </span>
          <span className="text-label-caps" style={{ color: 'var(--on-surface-variant)' }}>PATIENTS</span>
        </div>
        <div className="scenario-card-detail">
          <span><Activity size={12} /> {icu} ICU</span>
          <span>• {workflows} Workflows</span>
        </div>
      </div>
      
      <button 
        className="btn btn-danger-outline" 
        onClick={onSimulate}
        disabled={isSimulating}
      >
        <AlertTriangle size={16} />
        {isSimulating ? 'FAULT ACTIVE' : 'INJECT FAULT'}
      </button>
    </div>
  );
}


// ── Main Dashboard ──
export default function Dashboard() {
  const [services, setServices] = useState({});
  const [activeIncidentId, setActiveIncidentId] = useState(null);
  const [activeScenario, setActiveScenario] = useState(null);
  const [blastData, setBlastData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [remediationPlan, setRemediationPlan] = useState([]);
  const [briefings, setBriefings] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [complianceReport, setComplianceReport] = useState(null);
  const [incidentCreatedAt, setIncidentCreatedAt] = useState(null);
  const [incidentResolved, setIncidentResolved] = useState(false);
  const [health, setHealth] = useState([]);
  const [platform, setPlatform] = useState(null);
  const [chaosMessage, setChaosMessage] = useState(null);
  const knownIncidentRef = useRef(null);
  
  // 1. Fetch static service data on mount
  useEffect(() => {
    async function loadData() {
      try {
        setServices(await getServices());
      } catch (e) {
        console.error("Failed to load static data", e);
      }
    }
    loadData();
  }, []);

  // 2. Setup SSE for reasoning stream
  useEffect(() => {
    const cleanup = subscribeToReasoning(
      (msg) => {
        setLogs(prev => {
          return [...prev, {
            title: 'Agent Action',
            timestamp: new Date().toLocaleTimeString(),
            content: msg
          }];
        });
        
        // Poll the incident to get updated data when logs arrive
        if (activeIncidentId) {
          fetchIncidentData(activeIncidentId);
        }
      },
      () => console.log("SSE connected"),
      (err) => console.error("SSE error", err)
    );
    
    return cleanup;
  }, [activeIncidentId]);

  // 3. Poll live service health; pick up incidents the agent opens on its own
  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const status = await getStatus();
        if (cancelled) return;
        setHealth(status.service_health || []);
        setPlatform(status.platform);
        if (status.active_incident && status.active_incident !== knownIncidentRef.current) {
          knownIncidentRef.current = status.active_incident;
          setActiveIncidentId(status.active_incident);
          setChaosMessage(null);
          fetchIncidentData(status.active_incident);
        }
      } catch (e) {
        console.error("Failed to fetch status", e);
      }
    }
    poll();
    const interval = setInterval(poll, 3000);
    return () => { cancelled = true; clearInterval(interval); };
  }, []);

  async function fetchIncidentData(incidentId) {
    try {
      const inc = await getIncident(incidentId);
      
      // Set created timestamp for countdown
      if (inc.created_at) {
        setIncidentCreatedAt(inc.created_at);
      }
      
      // Check if resolved
      setIncidentResolved(inc.status === 'resolved');
      
      // Update scenario based on anomaly service
      if (inc.anomaly && inc.anomaly.service) {
        if (inc.anomaly.service.includes('vitals')) setActiveScenario('vitals');
        else if (inc.anomaly.service.includes('medication')) setActiveScenario('medication');
        else if (inc.anomaly.service.includes('lab')) setActiveScenario('labs');
      }
      
      if (inc.blast_radius) setBlastData(inc.blast_radius);
      if (inc.remediation_plan) setRemediationPlan(inc.remediation_plan);
      if (inc.briefings) setBriefings(inc.briefings);
      if (inc.notifications && inc.notifications.length > 0) setNotifications(inc.notifications);
      if (inc.compliance_report) setComplianceReport(inc.compliance_report);
      
      // Replace logs with actual audit trail
      if (inc.audit_trail) {
        const formattedLogs = inc.audit_trail.map(entry => ({
          title: entry.event_type.toUpperCase(),
          timestamp: new Date(entry.timestamp + 'Z').toLocaleTimeString(),
          content: entry.message,
          event_type: entry.event_type
        }));
        setLogs(formattedLogs);
      }
      
    } catch (e) {
      console.error("Failed to fetch incident details", e);
    }
  }

  const handleSimulate = async (scenarioType) => {
    let service = '';
    let failure_type = '';
    let severity = 'high';
    
    if (scenarioType === 'vitals') {
      service = 'vitals-ingestion';
      failure_type = 'memory_pressure';
    } else if (scenarioType === 'medication') {
      service = 'medication-alerts';
      failure_type = 'cpu_spike';
    } else if (scenarioType === 'labs') {
      service = 'lab-routing';
      failure_type = 'network_partition';
    }

    setLogs([]);
    setBlastData(null);
    setRemediationPlan([]);
    setBriefings(null);
    setNotifications([]);
    setComplianceReport(null);
    setActiveScenario(scenarioType);
    setIncidentResolved(false);
    setIncidentCreatedAt(new Date().toISOString());
    setActiveIncidentId(null);
    setChaosMessage(`Injecting ${failure_type} into ${service}...`);
    
    try {
      const res = await simulateFailure(service, failure_type, severity);
      setChaosMessage(
        `Fault live on ${res.service} (revision ${res.revision}). Servidor has not been told; ` +
        `waiting for its live probes to detect it...`
      );
    } catch (e) {
      console.error("Fault injection failed", e);
      setActiveScenario(null);
      setChaosMessage(null);
      setLogs([{ title: 'ERROR', timestamp: new Date().toLocaleTimeString(), content: `Fault injection failed: ${e.message}` }]);
    }
  };

  const getServiceStats = (svcKey) => {
    const svc = services[svcKey];
    if (!svc) return { patients: 0, icu: 0, workflows: 0 };
    return {
      patients: svc.total_patients || 0,
      icu: svc.icu_patients || 0,
      workflows: svc.workflows ? svc.workflows.length : 0
    };
  };

  const vitalsStats = getServiceStats('vitals-ingestion-svc');
  const medsStats = getServiceStats('medication-alerts-svc');
  const labsStats = getServiceStats('lab-routing-svc');

  const affectedService = activeScenario === 'vitals' ? 'vitals-ingestion' : 
    activeScenario === 'medication' ? 'medication-alerts' : 
    activeScenario === 'labs' ? 'lab-routing' : null;

  return (
    <div className="dashboard">
      {/* Countdown Timer — appears during active incidents */}
      {activeIncidentId && blastData && (
        <CountdownTimer 
          harmMinutes={blastData.estimated_harm_minutes} 
          startedAt={incidentCreatedAt}
          resolved={incidentResolved}
        />
      )}

      {/* Scenario Cards */}
      <div className="scenario-grid">
        <ScenarioCard 
          title="Vitals Monitoring"
          icon={Heart}
          colorClass="vitals"
          patients={vitalsStats.patients}
          icu={vitalsStats.icu}
          workflows={vitalsStats.workflows}
          isSimulating={activeScenario === 'vitals'}
          onSimulate={() => handleSimulate('vitals')}
        />
        <ScenarioCard 
          title="Medication Safety"
          icon={Pill}
          colorClass="medication"
          patients={medsStats.patients}
          icu={medsStats.icu}
          workflows={medsStats.workflows}
          isSimulating={activeScenario === 'medication'}
          onSimulate={() => handleSimulate('medication')}
        />
        <ScenarioCard 
          title="Lab Results"
          icon={FlaskConical}
          colorClass="labs"
          patients={labsStats.patients}
          icu={labsStats.icu}
          workflows={labsStats.workflows}
          isSimulating={activeScenario === 'labs'}
          onSimulate={() => handleSimulate('labs')}
        />
      </div>

      <ServiceHealthStrip health={health} platform={platform} />

      {chaosMessage && (
        <div className="card chaos-banner anim-slide-down">
          <AlertTriangle size={16} />
          <span>{chaosMessage}</span>
        </div>
      )}

      {/* Main Content */}
      <div className="dashboard-content">
        
        {/* Blast Radius + Dependency Graph side by side */}
        {blastData && (
          <div className="dashboard-impact-grid anim-scale-in anim-delay-1">
            <BlastRadius data={blastData} affectedService={affectedService} />
            <DependencyGraph affectedService={affectedService} />
          </div>
        )}

        {/* Briefings + Notifications side by side */}
        {(briefings || (notifications && notifications.length > 0)) && (
          <div className="dashboard-features-grid anim-slide-up anim-delay-3">
            {briefings && <IncidentBriefing briefings={briefings} />}
            {notifications && notifications.length > 0 && <NotificationLog notifications={notifications} />}
          </div>
        )}
        
        {/* Compliance Report */}
        {complianceReport && (
          <div className="anim-slide-up anim-delay-4">
            <ComplianceReport report={complianceReport} />
          </div>
        )}

        {/* Empty State */}
        {!blastData && !logs.length && (
          <div className="card dashboard-empty">
            <div className="dashboard-empty-icon">
              <Activity size={28} color="var(--on-surface-variant)" />
            </div>
            <span>Inject a fault into a live service above. Servidor detects it on its own.</span>
          </div>
        )}

        {/* Reasoning Timeline */}
        <ReasoningTimeline 
          logs={logs} 
          active={activeScenario !== null && (!complianceReport)} 
          remediationPlan={remediationPlan}
          incidentId={activeIncidentId}
          onStepApproved={async (stepOrder) => {
            await approveStep(activeIncidentId, stepOrder);
            fetchIncidentData(activeIncidentId);
          }}
          onStepRejected={async (stepOrder) => {
            await rejectStep(activeIncidentId, stepOrder);
            fetchIncidentData(activeIncidentId);
          }}
        />
      </div>
    </div>
  );
}
