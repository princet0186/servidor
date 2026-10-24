"""Real email delivery over SMTP (Gmail app password, Brevo, Resend SMTP, ...).

Every message goes to NOTIFY_EMAIL_TO, the demo on-call inbox. The synthetic clinical
staff in data/clinical_staff.json are listed inside the message as the intended
recipients but are never emailed, since their addresses are fictional.
"""
import asyncio
import logging
import smtplib
from email.message import EmailMessage

from config import (
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    NOTIFY_EMAIL_FROM, NOTIFY_EMAIL_TO, is_email_configured,
)

logger = logging.getLogger("servidor.email")


def _send_sync(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"Servidor Agent <{NOTIFY_EMAIL_FROM}>"
    msg["To"] = NOTIFY_EMAIL_TO
    msg.set_content(body)

    if SMTP_PORT == 465:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
            s.starttls()
            if SMTP_USER:
                s.login(SMTP_USER, SMTP_PASSWORD)
            s.send_message(msg)


async def send(subject: str, body: str) -> str:
    """Send one email. Returns 'sent', 'failed' or 'not_configured'."""
    if not is_email_configured():
        return "not_configured"
    try:
        await asyncio.to_thread(_send_sync, subject, body)
        logger.info(f"Email sent to {NOTIFY_EMAIL_TO}: {subject}")
        return "sent"
    except Exception as e:
        logger.error(f"Email delivery failed: {e}")
        return "failed"


def incident_alert(incident_id: str, service: str, problem: str, br: dict, notifications: list[dict]) -> tuple[str, str]:
    subject = (
        f"[SERVIDOR {br.get('severity', 'HIGH')}] {incident_id}: {service} — "
        f"{br.get('critical_patients', 0)} ICU patients at risk"
    )
    lines = [
        "SERVIDOR CLINICAL INCIDENT ALERT",
        "",
        f"Incident:            {incident_id}",
        f"Service:             {service}",
        f"Detected problem:    {problem}",
        f"Patients at risk:    {br.get('patients_at_risk', 0)}",
        f"ICU patients:        {br.get('critical_patients', 0)}",
        f"Estimated time to harm: {br.get('estimated_harm_minutes', '?')} minutes",
        f"Affected workflows:  {', '.join(br.get('affected_workflows', []))}",
        "",
        "Clinical staff paged (one message each):",
    ]
    for n in notifications:
        lines += ["", f"--- {n['recipient_role']}, {n['ward']} — {n['recipient_name']}", n["message"]]
    lines += ["", "Automated recovery is in progress. Risky steps wait for human approval in the Servidor console."]
    return subject, "\n".join(lines)


def approval_request(incident_id: str, service: str, steps: list[dict]) -> tuple[str, str]:
    subject = f"[SERVIDOR ACTION REQUIRED] {incident_id}: approval needed for {service}"
    lines = [f"The agent has paused before these steps on {service}:", ""]
    for s in steps:
        lines.append(f"  Step {s['order']} [{s['risk_level']}] {s['description']}")
    lines += ["", "Approve or reject them in the Servidor console."]
    return subject, "\n".join(lines)


def resolution(incident_id: str, service: str, duration_s: float, evidence: str) -> tuple[str, str]:
    subject = f"[SERVIDOR RESOLVED] {incident_id}: {service} recovered in {duration_s:.0f}s"
    body = (
        f"Incident {incident_id} on {service} is resolved.\n\n"
        f"Time to recovery: {duration_s:.0f}s\n"
        f"Verification: {evidence}\n\n"
        "Clinical teams can return to automated monitoring. A compliance report is available in the console."
    )
    return subject, body


def escalation(incident_id: str, service: str, evidence: str) -> tuple[str, str]:
    subject = f"[SERVIDOR ESCALATION] {incident_id}: {service} did not recover"
    body = (
        f"Automated remediation for {incident_id} on {service} did not restore service.\n\n"
        f"Last measurement: {evidence}\n\n"
        "Escalating to the on-call engineer. Keep clinical teams on manual monitoring."
    )
    return subject, body
