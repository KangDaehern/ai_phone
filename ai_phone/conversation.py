from __future__ import annotations

import re
from dataclasses import dataclass

from .models import CallRequest, OfficeConfig
from .config import normalize_phone


@dataclass(frozen=True)
class ParsedUtterance:
    call: CallRequest
    matched_employee: str | None
    matched_company: str | None


class TypedUtteranceParser:
    """음성 인식 결과를 흉내 내는 간단한 규칙 기반 파서."""

    def __init__(self, config: OfficeConfig):
        self.config = config
        self.company_by_phone = {
            normalize_phone(number): company.name
            for company in config.companies
            for number in company.phone_numbers
        }

    def parse(self, caller_number: str, utterance: str) -> ParsedUtterance:
        matched_employee = self._employee_name(utterance)
        matched_company = self._company_name(utterance) or self.company_by_phone.get(
            normalize_phone(caller_number)
        )
        caller_name = self._caller_name(utterance, matched_company)
        return ParsedUtterance(
            call=CallRequest(
                caller_number=caller_number,
                caller_name=caller_name,
                company_name=matched_company,
                purpose=utterance,
                requested_person=matched_employee,
            ),
            matched_employee=matched_employee,
            matched_company=matched_company,
        )

    def _employee_name(self, utterance: str) -> str | None:
        compact = utterance.replace(" ", "")
        for employee in self.config.employees:
            for candidate in (employee.name, *employee.aliases):
                if candidate.replace(" ", "") in compact:
                    return employee.name
        return None

    def _company_name(self, utterance: str) -> str | None:
        compact = utterance.replace(" ", "")
        for company in self.config.companies:
            if company.name.replace(" ", "") in compact:
                return company.name
        return None

    @staticmethod
    def _caller_name(utterance: str, company_name: str | None) -> str | None:
        working = utterance
        if company_name:
            working = working.replace(company_name, "")
        match = re.search(r"(?:저는\s*)?([가-힣]{2,4})(?:입니다|인데요|이에요|예요)", working)
        return match.group(1) if match else None

    def company_from_answer(self, answer: str) -> str | None:
        """업체명만 물은 후 받은 짧은 답변에서 업체명을 꺼낸다."""
        known = self._company_name(answer)
        if known:
            return known
        cleaned = re.sub(r"^(저는|여기는|저희는)\s*", "", answer.strip())
        cleaned = re.sub(r"\s*(입니다|인데요|이에요|예요)[.!?]?$", "", cleaned).strip()
        return cleaned or None

    @staticmethod
    def caller_name_from_answer(answer: str) -> str | None:
        """성함만 물은 후 받은 짧은 답변에서 이름을 꺼낸다."""
        cleaned = re.sub(r"^(저는|제\s*이름은)\s*", "", answer.strip())
        match = re.search(r"([가-힣]{2,4})(?:입니다|인데요|이에요|예요)?[.!?]?$", cleaned)
        return match.group(1) if match else None
