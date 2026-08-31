from __future__ import annotations

import json
from pathlib import Path

from .models import Company, Employee, EmployeeStatus, OfficeConfig, OfficeSettings


def normalize_phone(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def load_office_config(path: str | Path) -> OfficeConfig:
    config_path = Path(path)
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    office_raw = raw["office"]
    office = OfficeSettings(
        name=office_raw["name"],
        representative_number=office_raw["representative_number"],
        minimum_staff=int(office_raw["minimum_staff"]),
        maximum_staff=int(office_raw["maximum_staff"]),
        owner_id=office_raw["owner_id"],
        etc_employee_id=office_raw["etc_employee_id"],
        spam_reviewer_id=office_raw["spam_reviewer_id"],
        ring_timeout_seconds=int(office_raw["ring_timeout_seconds"]),
        common_services=tuple(office_raw["common_services"]),
    )
    employees = tuple(
        Employee(
            id=item["id"],
            name=item["name"],
            extension=item["extension"],
            role=item["role"],
            status=EmployeeStatus(item["status"]),
            aliases=tuple(item.get("aliases", [])),
            backup_employee_id=item.get("backup_employee_id"),
        )
        for item in raw["employees"]
    )
    companies = tuple(
        Company(
            id=item["id"],
            name=item["name"],
            phone_numbers=tuple(item.get("phone_numbers", [])),
            employee_id=item["employee_id"],
        )
        for item in raw["companies"]
    )
    spam = raw.get("spam", {})
    config = OfficeConfig(
        office=office,
        employees=employees,
        companies=companies,
        blocked_numbers=tuple(spam.get("blocked_numbers", [])),
        suspicious_keywords=tuple(spam.get("suspicious_keywords", [])),
    )
    validate_office_config(config)
    return config


def validate_office_config(config: OfficeConfig) -> None:
    regular_staff_count = sum(employee.id != config.office.owner_id for employee in config.employees)
    if not config.office.minimum_staff <= regular_staff_count <= config.office.maximum_staff:
        raise ValueError(
            f"대표를 제외한 직원 수는 {config.office.minimum_staff}~{config.office.maximum_staff}명이어야 합니다: "
            f"{regular_staff_count}"
        )

    employee_ids = [employee.id for employee in config.employees]
    if len(employee_ids) != len(set(employee_ids)):
        raise ValueError("직원 ID가 중복되었습니다.")
    if len({employee.extension for employee in config.employees}) != len(config.employees):
        raise ValueError("내선번호가 중복되었습니다.")

    required_ids = {
        config.office.owner_id,
        config.office.etc_employee_id,
        config.office.spam_reviewer_id,
    }
    missing = required_ids.difference(employee_ids)
    if missing:
        raise ValueError(f"필수 직원 ID가 없습니다: {sorted(missing)}")

    for employee in config.employees:
        if employee.backup_employee_id and employee.backup_employee_id not in employee_ids:
            raise ValueError(f"{employee.name}의 대체 담당자가 없습니다: {employee.backup_employee_id}")
    for company in config.companies:
        if company.employee_id not in employee_ids:
            raise ValueError(f"{company.name}의 담당자가 없습니다: {company.employee_id}")

    normalized_numbers = [
        normalize_phone(number)
        for company in config.companies
        for number in company.phone_numbers
    ]
    if len(normalized_numbers) != len(set(normalized_numbers)):
        raise ValueError("업체 전화번호가 중복되었습니다.")
