import React, { useState, useEffect } from 'react';
import ScenarioCard from '../components/ScenarioCard';
import BlastRadius from '../components/BlastRadius';
import ReasoningTimeline from '../components/ReasoningTimeline';
import IncidentBriefing from '../components/IncidentBriefing';
import NotificationLog from '../components/NotificationLog';
import ComplianceReport from '../components/ComplianceReport';
import { 
  getStatus, simulateFailure, subscribeToReasoning, getIncident, 
  getFacility, getDependencyGraph, approveStep, rejectStep
} from '../api/servidor';

export default function Dashboard() {
  const [services, setServices] = useState({});
  const [activeIncidentId, setActiveIncidentId] = useState(null);
  const [activeScenario, setActiveScenario] = useState(null); // 'vitals', 'medication', 'labs'
  const [blastData, setBlastData] = useState(null);
  const [logs, setLogs] = useState([]);
  const [remediationPlan, setRemediationPlan] = useState([]);
  const [briefings, setBriefings] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [complianceReport, setComplianceReport] = useState(null);
  
  // 1. Fetch static service data on mount
  useEffect(() => {
    async function loadData() {
      try {
        const res = await fetch('/api/v1/services');
        if (res.ok) {
          const svcMap = await res.json();
          setServices(svcMap);
        }
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
          // If it's a step approval prompt, handle specially later if needed
          return [...prev, {
            title: 'Agent Action',
            timestamp: new Date().toLocaleTimeString(),
            content: msg
          }];
        });
        
        // Polling the incident to get updated data when logs arrive
        if (activeIncidentId) {
          fetchIncidentData(activeIncidentId);
        }
      },
      () => console.log("SSE connected"),
      (err) => console.error("SSE error", err)
    );
    
    return cleanup;
  }, [activeIncidentId]);

  // 3. Check for existing active incident on mount
  useEffect(() => {
    async function checkStatus() {
      try {
        const status = await getStatus();
        if (status.active_incident) {
          setActiveIncidentId(status.active_incident);
          fetchIncidentData(status.active_incident);
        }
      } catch (e) {
        console.error("Failed to fetch status", e);
      }
    }
    checkStatus();
  }, []);

  async function fetchIncidentData(incidentId) {
    try {
      const inc = await getIncident(incidentId);
      
      // Update scenario based on anomaly service
      if (inc.anomaly && inc.anomaly.service) {
        if (inc.anomaly.service.includes('vitals')) setActiveScenario('vitals');
        else if (inc.anomaly.service.includes('medication')) setActiveScenario('medication');
        else if (inc.anomaly.service.includes('lab')) setActiveScenario('labs');
      }
      
      // Update blast radius
      if (inc.blast_radius) {
        setBlastData(inc.blast_radius);
      }
      
      // Update plan
      if (inc.remediation_plan) {
        setRemediationPlan(inc.remediation_plan);
      }
      
      // Update features
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
    
    try {
      const res = await simulateFailure(service, failure_type, severity);
      setActiveIncidentId(res.incident_id);
    } catch (e) {
      console.error("Simulation failed", e);
      setLogs([{ title: 'ERROR', timestamp: new Date().toLocaleTimeString(), content: `Simulation failed: ${e.message}` }]);
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

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', height: '100%', overflowY: 'auto', paddingRight: '4px' }}>
      {/* Top Section - Scenarios */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--spacing-md)' }}>
        <ScenarioCard 
          title="Vitals Monitoring"
          patients={vitalsStats.patients}
          icu={vitalsStats.icu}
          workflows={vitalsStats.workflows}
          isSimulating={activeScenario === 'vitals'}
          onSimulate={() => handleSimulate('vitals')}
        />
        <ScenarioCard 
          title="Medication Safety"
          patients={medsStats.patients}
          icu={medsStats.icu}
          workflows={medsStats.workflows}
          isSimulating={activeScenario === 'medication'}
          onSimulate={() => handleSimulate('medication')}
        />
        <ScenarioCard 
          title="Lab Results"
          patients={labsStats.patients}
          icu={labsStats.icu}
          workflows={labsStats.workflows}
          isSimulating={activeScenario === 'labs'}
          onSimulate={() => handleSimulate('labs')}
        />
      </div>

      {/* Main Content Area (Single Column) */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-lg)', flex: 1, minHeight: 0, overflowY: 'auto', paddingBottom: 'var(--spacing-lg)' }}>
        
        {blastData && (
          <BlastRadius 
            data={blastData} 
            affectedService={
              activeScenario === 'vitals' ? 'vitals-ingestion' : 
              activeScenario === 'medication' ? 'medication-alerts' : 'lab-routing'
            } 
          />
        )}
        
        {/* Feature 4: Briefings */}
        {briefings && (
          <IncidentBriefing briefings={briefings} />
        )}
        
        {/* Feature 6: Notifications */}
        {notifications && notifications.length > 0 && (
          <NotificationLog notifications={notifications} />
        )}
        
        {/* Feature 7: Compliance Report */}
        {complianceReport && (
          <ComplianceReport report={complianceReport} />
        )}

        {!blastData && !logs.length && (
          <div className="card" style={{ height: '300px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--on-surface-variant)' }}>
            Select a scenario to simulate failure
          </div>
        )}

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
