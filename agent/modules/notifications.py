"""Feature 6: Clinical notification dispatcher.

Generates and dispatches notifications to clinical staff when a service failure
impacts patient care. Each staff message is delivered for real by email to the demo
on-call inbox (see modules/email_alerts.py); staff phone numbers and addresses are synthetic.
"""
from models import ClinicalNotification, AuditEventType
from state import add_audit, get_stream_queue
from database import get_clinical_staff, store_notifications, get_service_patient_map
from datetime import datetime
import logging

logger = logging.getLogger("servidor.notifications")


async def _emit(msg: str):
    q = get_stream_queue()
    await q.put(msg)


_MESSAGE_TEMPLATES = {
    "sms": (
        "SERVIDOR ALERT: {service_name} is experiencing {failure_type}. "
        "{icu_count} ICU patients in {ward} may need manual monitoring. "
        "Affected beds: {beds}. Estimated resolution: {eta} min."
    ),
    "email": (
        "SERVIDOR INCIDENT ALERT\n\n"
        "Service: {service_name}\n"
        "Issue: {failure_type}\n"
        "Patients at risk: {total_patients}\n"
        "ICU patients affected: {icu_count}\n"
        "Estimated time to harm: {eta} minutes\n\n"
        "Automated recovery is in progress. You will be notified upon resolution."
    ),
}


def _get_beds_for_ward(icu_locations: list[dict], ward_id: str) -> str:
    """Extract bed IDs for a specific ward."""
    beds = [loc["bed"] for loc in icu_locations if loc.get("ward") == ward_id]
    return ", ".join(beds) if beds else "all monitored beds"


async def dispatch_notifications(
    incident_id: str,
    service_id: str,
    anomaly: dict,
    blast_radius_data: dict,
) -> list[dict]:
    """Generate and 'send' clinical notifications. Returns list of notification records."""

    await _emit("")
    await _emit("Dispatching clinical notifications...")

    staff = get_clinical_staff(service_id)
    if not staff:
        # Try fuzzy match
        spm = get_service_patient_map()
        for key in spm:
            if service_id.replace("-svc", "") in key:
                staff = get_clinical_staff(key)
                break

    if not staff:
        await _emit("  No clinical staff registered for this service")
        return []

    icu_locations = blast_radius_data.get("icu_locations", [])
    service_context = get_service_patient_map().get(service_id, {})
    display_name = service_context.get("display_name", service_id)
    failure_type = anomaly.get("problem", anomaly.get("failure_type", "service degradation"))
    eta = blast_radius_data.get("estimated_harm_minutes", 15)

    notifications = []

    for person in staff:
        channel = person.get("notification_channel", "sms")
        ward_id = person.get("ward_id", "")
        ward_name = person.get("ward", ward_id)
        beds_str = _get_beds_for_ward(icu_locations, ward_id)

        template = _MESSAGE_TEMPLATES.get(channel, _MESSAGE_TEMPLATES["sms"])
        message = template.format(
            service_name=display_name,
            failure_type=failure_type,
            icu_count=blast_radius_data.get("critical_patients", 0),
            total_patients=blast_radius_data.get("patients_at_risk", 0),
            ward=ward_name,
            beds=beds_str,
            eta=eta,
        )

        notification = ClinicalNotification(
            recipient_name=person["name"],
            recipient_role=person["role"],
            ward=ward_name,
            channel=channel,
            message=message,
        )

        notifications.append(notification.model_dump(mode="json"))

        icon = "📱" if channel == "sms" else "📧"
        await _emit(f"  {icon} {person['role']}, {ward_name} — {person['name']}")

    # Deliver: one real email to the on-call inbox carrying every staff message
    from modules import email_alerts
    subject, body = email_alerts.incident_alert(
        incident_id, display_name, failure_type, blast_radius_data, notifications
    )
    delivery = await email_alerts.send(subject, body)
    for n in notifications:
        n["delivery"] = "email" if delivery == "sent" else delivery
        n["status"] = "sent" if delivery == "sent" else ("failed" if delivery == "failed" else "logged")
    if delivery == "sent":
        await _emit("  Alert email delivered to the on-call inbox")
    elif delivery == "failed":
        await _emit("  Warning: alert email delivery FAILED (check SMTP settings)")
    else:
        await _emit("  Email not configured: notifications logged only")

    # Persist
    await store_notifications(incident_id, notifications)

    add_audit(
        incident_id, AuditEventType.NOTIFICATION,
        f"Dispatched {len(notifications)} clinical notifications",
        confidence=1.0,
        details={"count": len(notifications), "delivery": delivery},
    )

    await _emit(f"  {len(notifications)} notifications dispatched")
    return notifications
