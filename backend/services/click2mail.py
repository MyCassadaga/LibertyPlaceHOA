from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from ..config import settings
from ..models.models import Notice, Owner

logger = logging.getLogger(__name__)


class Click2MailError(RuntimeError):
    pass


ADDRESS_RE = re.compile(
    r"^(?P<street>.+?),\s*(?P<city>[A-Za-z .'-]+?),\s*(?P<state>[A-Z]{2})\s*(?P<postal>\d{5}(?:-\d{4})?)$"
)


@dataclass
class ParsedAddress:
    address1: str
    address2: Optional[str]
    city: str
    state: str
    postal: str
    country: str = "US"


class Click2MailClient:
    def __init__(self) -> None:
        self._timeout = httpx.Timeout(45.0)

    @property
    def is_configured(self) -> bool:
        return settings.click2mail_is_configured

    @property
    def _base_url(self) -> str:
        return f"https://{settings.click2mail_subdomain}.click2mail.com/molpro"

    def _http_client(self) -> httpx.Client:
        if not self.is_configured:
            raise Click2MailError("Click2Mail integration is not configured.")
        return httpx.Client(
            base_url=self._base_url,
            auth=(settings.click2mail_username, settings.click2mail_password),
            timeout=self._timeout,
        )

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        with self._http_client() as client:
            response = client.request(method, path, **kwargs)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text
            logger.error("Click2Mail API error (%s %s): %s", method, path, detail)
            raise Click2MailError(f"Click2Mail API responded with {exc.response.status_code}: {detail}") from exc
        try:
            data = response.json()
        except ValueError:
            raise Click2MailError("Unexpected response from Click2Mail API (non-JSON).")
        return data

    def upload_document(self, filename: str, content: bytes) -> str:
        params = {
            "documentName": filename,
            "documentClass": "Letter 8.5 x 11",
            "documentFormat": "PDF",
        }
        files = {"file": (filename, content, "application/pdf")}
        data = self._request("POST", "/documents", params=params, files=files)
        document_id = data.get("id") or data.get("documentId")
        if not document_id:
            raise Click2MailError("Click2Mail did not return a document ID.")
        return str(document_id)

    def create_address_list(self, owner: Owner, notice: Notice, parsed: ParsedAddress) -> str:
        name = f"owner-{owner.id}-notice-{notice.id}"
        csv_buffer = io.StringIO()
        writer = csv.writer(csv_buffer)
        writer.writerow(["First Name", "Last Name", "Organization", "Address1", "Address2", "City", "State", "Zip", "Country"])
        first, last = _split_name(owner.primary_name)
        writer.writerow(
            [
                first,
                last,
                owner.secondary_name or "",
                parsed.address1,
                parsed.address2 or "",
                parsed.city,
                parsed.state,
                parsed.postal,
                parsed.country,
            ]
        )
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        data = {
            "addressListName": name,
            "addressListType": "Residential",
            "description": f"Auto-generated for notice {notice.id}",
            "encoding": "UTF-8",
            "hasHeaders": "true",
        }
        files = {"file": (f"{name}.csv", csv_bytes, "text/csv")}
        response = self._request("POST", "/addressLists", data=data, files=files)
        list_id = response.get("id") or response.get("addressListId")
        if not list_id:
            raise Click2MailError("Click2Mail did not return an address list ID.")
        return str(list_id)

    def create_job(self, *, document_id: str, address_list_id: str) -> Dict[str, Any]:
        params = {
            "documentClass": "Letter 8.5 x 11",
            "layout": "Address on First Page",
            "envelope": "#10 Double Window",
            "color": "Black and White",
            "paperType": "White 24#",
            "printOption": "Printing One side",
            "documentId": document_id,
            "addressId": address_list_id,
            "mailClass": "First Class",
            "productionTime": "Next Day",
        }
        params.update(_return_address_params())
        data = self._request("POST", "/jobs", params=params)
        return data

    def dispatch_notice(self, notice: Notice, owner: Owner, pdf_bytes: bytes) -> Dict[str, Any]:
        if not self.is_configured:
            raise Click2MailError("Click2Mail integration is not configured.")
        parsed = _parse_owner_address(owner)
        document_id = self.upload_document(f"notice-{notice.id}.pdf", pdf_bytes)
        address_list_id = self.create_address_list(owner, notice, parsed)
        job = self.create_job(document_id=document_id, address_list_id=address_list_id)
        logger.info(
            "Click2Mail job created for notice %s (document=%s, addressList=%s, job=%s)",
            notice.id,
            document_id,
            address_list_id,
            job.get("id"),
        )
        return job


def _split_name(name: str) -> tuple[str, str]:
    parts = [segment for segment in name.split() if segment]
    if not parts:
        return ("Resident", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[0], " ".join(parts[1:]))


def _parse_owner_address(owner: Owner) -> ParsedAddress:
    raw = owner.mailing_address or owner.property_address
    if not raw:
        raise Click2MailError("Owner is missing a mailing or property address.")
    normalized = raw.replace("\n", ",").strip()
    match = ADDRESS_RE.match(normalized)
    if match:
        return ParsedAddress(
            address1=match.group("street"),
            address2=None,
            city=match.group("city"),
            state=match.group("state"),
            postal=match.group("postal"),
        )
    if settings.click2mail_default_city and settings.click2mail_default_state and settings.click2mail_default_postal:
        return ParsedAddress(
            address1=normalized,
            address2=None,
            city=settings.click2mail_default_city,
            state=settings.click2mail_default_state,
            postal=settings.click2mail_default_postal,
        )
    raise Click2MailError(
        "Unable to parse owner address. Provide a full 'Street, City, ST ZIP' format "
        "or configure CLICK2MAIL_DEFAULT_* fallbacks."
    )


def _return_address_params() -> Dict[str, Optional[str]]:
    return {
        "rtnName": settings.click2mail_return_name or "Liberty Place HOA",
        "rtnOrganization": settings.click2mail_return_company or "",
        "rtnaddress1": settings.click2mail_return_address1 or "",
        "rtnaddress2": settings.click2mail_return_address2 or "",
        "rtnCity": settings.click2mail_return_city or "",
        "rtnState": settings.click2mail_return_state or "",
        "rtnZip": settings.click2mail_return_postal or "",
    }


click2mail_client = Click2MailClient()
