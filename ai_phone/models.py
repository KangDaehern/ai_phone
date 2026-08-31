from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EmployeeStatus(StrEnum):
    AVAILABLE = "available"
    BUSY = "busy"
    MEETING = "meeting"
    AWAY = "away"
    VACATION = "vacation"
    OFF_DUTY = "off_duty"


class RouteKind(StrEnum):
    DIRECT_NUMBER_MATCH = "direct_number_match"
    REQUESTED_PERSON = "requested_person"
    COMPANY_MATCH = "company_match"
    OWNER_REQUEST = "owner_request"
    FALLBACK = "fallback"
    SPAM_BLOCKED = "spam_blocked"
    SPAM_REVIEW = "spam_review"


@dataclass(frozen=True)
class Employee:
    id: str
    name: str
    extension: str
    role: str
    status: EmployeeStatus
    aliases: tuple[str, ...] = ()
    backup_employee_id: str | None = None

    @property
    def is_available(self) -> bool:
        return self.status == EmployeeStatus.AVAILABLE


@dataclass(frozen=True)
class Company:
    id: str
    name: str
    phone_numbers: tuple[str, ...]
    employee_id: str


@dataclass(frozen=True)
class OfficeSettings:
    name: str
    representative_number: str
    minimum_staff: int
    maximum_staff: int
    owner_id: str
    etc_employee_id: str
    spam_reviewer_id: str
    ring_timeout_seconds: int
    common_services: tuple[str, ...]


@dataclass(frozen=True)
class OfficeConfig:
    office: OfficeSettings
    employees: tuple[Employee, ...]
    companies: tuple[Company, ...]
    blocked_numbers: tuple[str, ...]
    suspicious_keywords: tuple[str, ...]


@dataclass(frozen=True)
class CallRequest:
    caller_number: str
    caller_name: str | None = None
    company_name: str | None = None
    purpose: str | None = None
    requested_person: str | None = None


@dataclass(frozen=True)
class RouteDecision:
    kind: RouteKind
    target: Employee | None
    original_target: Employee | None
    company: Company | None
    reason: str
    confidence: float
    preconnect_announcement: str | None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CallOutcome:
    decision: RouteDecision
    transfer_status: str
    callback_created: bool
    caller_message: str
    notification: str | None

