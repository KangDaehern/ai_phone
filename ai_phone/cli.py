from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from .adapters import DummyNotificationAdapter, DummyTelephonyAdapter, DummyVoiceAdapter
from .config import load_office_config
from .models import CallRequest
from .routing import RoutingEngine
from .service import CallService


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "office.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 대표전화 더미 라우팅 시뮬레이터")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--caller", required=True, help="발신번호")
    parser.add_argument("--caller-name", help="발신자 이름")
    parser.add_argument("--company", help="업체명")
    parser.add_argument("--purpose", help="통화 용건")
    parser.add_argument("--request-person", help="찾는 직원 또는 대표")
    parser.add_argument(
        "--status",
        action="append",
        default=[],
        metavar="직원명=상태",
        help="상태 덮어쓰기: available, busy, meeting, away, vacation, off_duty",
    )
    parser.add_argument("--simulate-no-answer", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_office_config(args.config)
    routing = RoutingEngine(config)
    for status_value in args.status:
        try:
            employee_name, status = status_value.split("=", 1)
        except ValueError as error:
            raise SystemExit("--status 형식은 직원명=상태입니다.") from error
        routing = routing.with_status(employee_name, status)

    service = CallService(
        routing=routing,
        telephony=DummyTelephonyAdapter(answer_transfer=not args.simulate_no_answer),
        notification=DummyNotificationAdapter(),
        voice=DummyVoiceAdapter(),
    )
    outcome = service.handle(
        CallRequest(
            caller_number=args.caller,
            caller_name=args.caller_name,
            company_name=args.company,
            purpose=args.purpose,
            requested_person=args.request_person,
        )
    )
    print("\n[결과]")
    print(json.dumps(asdict(outcome), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
