from __future__ import annotations

import logging
from typing import Any, Dict

from ..config import settings
from ..models.models import Notice, Owner

logger = logging.getLogger(__name__)


class CertifiedMailError(RuntimeError):
    pass


class CertifiedMailClient:
    @property
    def is_configured(self) -> bool:
        return settings.certified_mail_enabled

    def dispatch_notice(self, notice: Notice, owner: Owner, pdf_bytes: bytes) -> Dict[str, Any]:
        if not self.is_configured:
            raise CertifiedMailError("Certified mail integration is not configured.")
        logger.info(
            "Certified mail dispatch queued for notice %s (owner=%s, bytes=%s)",
            notice.id,
            owner.id,
            len(pdf_bytes),
        )
        return {
            "status": "QUEUED",
            "trackingNumber": f"CM-{notice.id}",
        }


certified_mail_client = CertifiedMailClient()
