from __future__ import annotations

from dataclasses import replace

from .config import normalize_phone
from .models import CallRequest, Company, Employee, OfficeConfig, RouteDecision, RouteKind


class RoutingEngine:
    def __init__(self, config: OfficeConfig):
        self.config = config
        self.employees = {employee.id: employee for employee in config.employees}
        self.owner = self.employees[config.office.owner_id]
        self.etc_employee = self.employees[config.office.etc_employee_id]
        self.spam_reviewer = self.employees[config.office.spam_reviewer_id]
        self.company_by_phone = {
            normalize_phone(number): company
            for company in config.companies
            for number in company.phone_numbers
        }
        self.blocked_numbers = {normalize_phone(number) for number in config.blocked_numbers}

    def decide(self, call: CallRequest) -> RouteDecision:
        normalized_caller = normalize_phone(call.caller_number)
        if normalized_caller in self.blocked_numbers:
            return RouteDecision(
                kind=RouteKind.SPAM_BLOCKED,
                target=None,
                original_target=None,
                company=None,
                reason="확정 스팸 번호",
                confidence=1.0,
                preconnect_announcement=None,
                metadata={"spam_reviewer": self.spam_reviewer.name},
            )

        if self._is_suspicious(call.purpose):
            return RouteDecision(
                kind=RouteKind.SPAM_REVIEW,
                target=None,
                original_target=None,
                company=self._find_company(call),
                reason="의심 스팸 키워드 감지",
                confidence=0.8,
                preconnect_announcement=None,
                metadata={"spam_reviewer": self.spam_reviewer.name},
            )

        requested = self._find_employee(call.requested_person)
        if requested:
            kind = RouteKind.OWNER_REQUEST if requested.id == self.owner.id else RouteKind.REQUESTED_PERSON
            return self._route_to_available(
                requested,
                kind,
                self._find_company(call),
                "발신자가 특정 담당자를 요청함",
                0.98,
                call,
            )

        if self._owner_requested(call):
            return self._route_to_available(
                self.owner,
                RouteKind.OWNER_REQUEST,
                self._find_company(call),
                "대표/사장 연결 요청",
                0.95,
                call,
            )

        phone_company = self.company_by_phone.get(normalized_caller)
        if phone_company:
            return self._route_to_available(
                self.employees[phone_company.employee_id],
                RouteKind.DIRECT_NUMBER_MATCH,
                phone_company,
                "등록된 발신번호의 업체 담당자",
                1.0,
                call,
            )

        company = self._find_company(call)
        if company:
            return self._route_to_available(
                self.employees[company.employee_id],
                RouteKind.COMPANY_MATCH,
                company,
                "발신자가 말한 업체의 담당자",
                0.92,
                call,
            )

        return self._route_to_available(
            self.etc_employee,
            RouteKind.FALLBACK,
            None,
            "업체 또는 담당자를 확인할 수 없어 기타 담당자에게 배정",
            0.35,
            call,
        )

    def with_status(self, employee_name: str, status: str) -> "RoutingEngine":
        target = self._find_employee(employee_name)
        if not target:
            raise ValueError(f"직원을 찾을 수 없습니다: {employee_name}")
        updated = tuple(
            replace(employee, status=type(employee.status)(status)) if employee.id == target.id else employee
            for employee in self.config.employees
        )
        return RoutingEngine(replace(self.config, employees=updated))

    def _route_to_available(
        self,
        target: Employee,
        kind: RouteKind,
        company: Company | None,
        reason: str,
        confidence: float,
        call: CallRequest,
    ) -> RouteDecision:
        original = target
        if not target.is_available:
            backup = self.employees.get(target.backup_employee_id or "")
            if backup and backup.is_available:
                target = backup
                reason += f"; {original.name} 상태가 {original.status.value}이므로 대체 담당자 선택"
            elif self.etc_employee.is_available:
                target = self.etc_employee
                reason += f"; {original.name} 부재로 기타 담당자 선택"
            else:
                reason += "; 연결 가능한 직원 없음"

        announcement = self._announcement(call, company)
        return RouteDecision(
            kind=kind,
            target=target if target.is_available else None,
            original_target=original,
            company=company,
            reason=reason,
            confidence=confidence,
            preconnect_announcement=announcement,
        )

    def _find_employee(self, value: str | None) -> Employee | None:
        if not value:
            return None
        compact = value.replace(" ", "")
        for employee in self.config.employees:
            candidates = (employee.name, employee.extension, *employee.aliases)
            if any(candidate.replace(" ", "") in compact for candidate in candidates):
                return employee
        return None

    def _find_company(self, call: CallRequest) -> Company | None:
        if call.company_name:
            compact = call.company_name.replace(" ", "")
            for company in self.config.companies:
                if company.name.replace(" ", "") in compact or compact in company.name.replace(" ", ""):
                    return company
        return self.company_by_phone.get(normalize_phone(call.caller_number))

    def _owner_requested(self, call: CallRequest) -> bool:
        combined = " ".join(filter(None, (call.requested_person, call.purpose)))
        return any(keyword in combined for keyword in ("대표", "사장", "대표님", "사장님"))

    def _is_suspicious(self, purpose: str | None) -> bool:
        return bool(purpose and any(keyword in purpose for keyword in self.config.suspicious_keywords))

    @staticmethod
    def _announcement(call: CallRequest, company: Company | None) -> str:
        caller = call.caller_name or "성함 미확인"
        company_name = company.name if company else (call.company_name or "업체 미확인")
        purpose = call.purpose or "용건 미확인"
        return f"{company_name} {caller}님, {purpose}입니다."

