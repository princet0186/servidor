import React from 'react';

function deliveryLabel(n) {
  if (n.delivery === 'email') return 'DELIVERED BY EMAIL';
  if (n.status === 'failed') return 'DELIVERY FAILED';
  return 'LOGGED (EMAIL NOT CONFIGURED)';
}

function deliveryColor(status) {
  if (status === 'sent') return 'var(--status-safe)';
  if (status === 'failed') return 'var(--status-critical)';
  return 'var(--on-surface-variant)';
}

export default function NotificationLog({ notifications }) {
  if (!notifications || notifications.length === 0) return null;

  return (
    <div className="card notification-card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div className="notification-header">
        <h2 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          Clinical Notifications
        </h2>
        <span className="text-label-caps" style={{ color: deliveryColor(notifications[0].status) }}>
          {notifications.length} {deliveryLabel(notifications[0])}
        </span>
      </div>
      
      <div className="notification-list">
        {notifications.map((notif, i) => (
          <div key={i} className="notification-item">
            <div className="notification-item-header">
              <div className="notification-item-badges">
                <span className="text-label-caps notification-channel-badge">
                  {notif.channel.toUpperCase()}
                </span>
                <span style={{ fontWeight: 600 }}>{notif.recipient_name}</span>
                <span style={{ color: 'var(--on-surface-variant)' }}>({notif.recipient_role})</span>
              </div>
              <span className="text-data-mono" style={{ color: 'var(--on-surface-variant)' }}>
                {notif.ward}
              </span>
            </div>
            <div className="text-body-base notification-message">
              "{notif.message}"
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
