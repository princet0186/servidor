import React from 'react';

export default function NotificationLog({ notifications }) {
  if (!notifications || notifications.length === 0) return null;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          Clinical Notifications Dispatched
        </h2>
        <span className="text-label-caps" style={{ color: 'var(--primary)' }}>
          {notifications.length} SENT
        </span>
      </div>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-sm)' }}>
        {notifications.map((notif, i) => (
          <div key={i} style={{ 
            padding: 'var(--spacing-md)', 
            background: 'var(--surface-container-lowest)', 
            border: '1px solid var(--outline-variant)',
            borderRadius: 'var(--radius)',
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--spacing-sm)'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div style={{ display: 'flex', gap: 'var(--spacing-sm)', alignItems: 'center' }}>
                <span className="text-label-caps" style={{ 
                  background: 'var(--surface-container-high)', 
                  padding: '2px 6px', 
                  borderRadius: 'var(--radius-sm)' 
                }}>
                  {notif.channel.toUpperCase()}
                </span>
                <span style={{ fontWeight: 600 }}>{notif.recipient_name}</span>
                <span style={{ color: 'var(--on-surface-variant)' }}>({notif.recipient_role})</span>
              </div>
              <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)' }}>
                {notif.ward}
              </span>
            </div>
            <div className="text-body-base" style={{ color: 'var(--on-surface-variant)', fontStyle: 'italic' }}>
              "{notif.message}"
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
