from typing import Iterable, List


def send_announcement(subject: str, body: str, recipients: Iterable[str]) -> List[str]:
    """Placeholder email sender. Returns list of emails that would be notified."""
    sent_to = [email for email in recipients if email]
    # In production integrate with transactional email provider.
    return sent_to
