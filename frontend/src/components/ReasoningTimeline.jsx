import React, { useState } from 'react';
import { CheckCircle, Hourglass, ChevronRight, ChevronDown } from 'lucide-react';

export default function ReasoningTimeline({ logs, active, remediationPlan, onStepApproved, onStepRejected }) {
  const [expandedIndex, setExpandedIndex] = useState(logs?.length - 1 || 0);
  
  const pendingSteps = remediationPlan?.filter(s => s.status === 'pending') || [];
  
  return (
    <div className="reasoning-section">
      <h2 className="text-label-caps reasoning-header">
        AGENT REASONING TIMELINE
      </h2>
      
      <div className="reasoning-timeline">
        {(!logs || logs.length === 0) && (
          <div className="text-body-base reasoning-empty">
            Waiting for events...
          </div>
        )}
        
        {logs?.map((log, i) => {
          const isLast = i === logs.length - 1 && pendingSteps.length === 0;
          const isExpanded = expandedIndex === i;
          
          let dotClass = 'safe';
          let Icon = CheckCircle;
          let iconColor = 'var(--status-safe)';
          
          if (log.event_type === 'refusal') {
            dotClass = 'critical';
            iconColor = 'var(--status-critical)';
          }
          if (log.event_type === 'rejection') {
            dotClass = 'warning';
            iconColor = 'var(--status-warning)';
          }
          
          return (
            <div key={i} className="reasoning-entry" style={{ animationDelay: `${Math.min(i * 0.05, 0.5)}s` }}>
              <div className="reasoning-connector">
                <div className={`status-dot ${dotClass}`}></div>
                {!isLast && <div className="reasoning-line"></div>}
              </div>
              
              <div className="reasoning-body" style={{ paddingBottom: isLast ? '0' : 'var(--spacing-lg)' }}>
                <div className="reasoning-meta">
                  <div className="reasoning-meta-left">
                    <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)' }}>{log.timestamp}</span>
                    <span className="text-body-base" style={{ fontWeight: 600, color: 'var(--primary)' }}>{log.title}</span>
                  </div>
                  <Icon size={20} color={iconColor} />
                </div>
                
                <div className="text-body-base reasoning-snippet">
                  {log.content.split('\n')[0]}
                </div>
                
                {log.content.includes('\n') && (
                  <button 
                    className="reasoning-expand-btn"
                    onClick={() => setExpandedIndex(isExpanded ? -1 : i)}
                  >
                    {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    <span>Expand reasoning</span>
                  </button>
                )}
                
                {isExpanded && log.content.includes('\n') && (
                  <div className="text-data-mono reasoning-expanded-content">
                    {log.content.substring(log.content.indexOf('\n') + 1)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        
        {/* Pending approval cards */}
        {pendingSteps.map((step, i) => (
          <div key={`pending-${i}`} className="reasoning-pending">
            <div className="reasoning-connector">
              <div className="status-dot warning" style={{ marginTop: '8px' }}></div>
            </div>
            
            <div className="reasoning-pending-body">
              <div className="reasoning-meta">
                <div className="reasoning-meta-left">
                  <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)' }}>
                    {new Date().toLocaleTimeString('en-US', { hour12: false })}
                  </span>
                  <span className="text-body-base" style={{ fontWeight: 600, color: 'var(--primary)' }}>Waiting for approval...</span>
                </div>
                <Hourglass size={20} color="var(--status-warning)" />
              </div>
              
              <div className="text-body-base reasoning-snippet">
                Step {step.order}: {step.action} ({step.risk_level.toLowerCase()} risk)
              </div>
              
              <div className="reasoning-pending-actions">
                <button className="btn-approve" onClick={() => onStepApproved(step.order)}>
                  APPROVE
                </button>
                <button className="btn-reject" onClick={() => onStepRejected(step.order)}>
                  REJECT
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
