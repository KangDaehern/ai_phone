from __future__ import annotations

import unittest
from pathlib import Path

from ai_phone.adapters import DummyNotificationAdapter, DummyTelephonyAdapter, DummyVoiceAdapter
from ai_phone.config import load_office_config
from ai_phone.conversation import TypedUtteranceParser
from ai_phone.models import CallRequest, RouteKind
from ai_phone.routing import RoutingEngine
from ai_phone.service import CallService


CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "office.json"


class RoutingEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_office_config(CONFIG_PATH)

    def setUp(self) -> None:
        self.routing = RoutingEngine(self.config)

    def test_config_has_owner_and_nine_employees(self) -> None:
        self.assertEqual(len(self.config.employees), 10)
        self.assertEqual(sum(employee.id != "owner" for employee in self.config.employees), 9)
        self.assertEqual(self.routing.owner.name, "홍사장")

    def test_registered_number_routes_without_ai_discovery(self) -> None:
        decision = self.routing.decide(CallRequest(caller_number="02-555-1001", purpose="부가세 문의"))
        self.assertEqual(decision.kind, RouteKind.DIRECT_NUMBER_MATCH)
        self.assertEqual(decision.target.name, "홍길원")
        self.assertEqual(decision.confidence, 1.0)

    def test_company_name_routes_to_assigned_employee(self) -> None:
        decision = self.routing.decide(
            CallRequest(caller_number="010-7777-7777", company_name="해든학원", purpose="급여 처리")
        )
        self.assertEqual(decision.kind, RouteKind.COMPANY_MATCH)
        self.assertEqual(decision.target.name, "홍길팔")

    def test_owner_request_routes_to_owner(self) -> None:
        decision = self.routing.decide(
            CallRequest(caller_number="010-7777-7777", purpose="사장님과 통화하고 싶습니다")
        )
        self.assertEqual(decision.kind, RouteKind.OWNER_REQUEST)
        self.assertEqual(decision.target.name, "홍사장")
        self.assertEqual(decision.target.extension, "100")

    def test_unavailable_employee_routes_to_backup(self) -> None:
        routing = self.routing.with_status("홍길원", "vacation")
        decision = routing.decide(CallRequest(caller_number="02-555-1001", purpose="신고 문의"))
        self.assertEqual(decision.original_target.name, "홍길원")
        self.assertEqual(decision.target.name, "홍길둘")

    def test_unknown_caller_routes_to_etc_employee(self) -> None:
        decision = self.routing.decide(CallRequest(caller_number="010-8888-8888", purpose="일반 문의"))
        self.assertEqual(decision.kind, RouteKind.FALLBACK)
        self.assertEqual(decision.target.name, "홍길구")

    def test_confirmed_spam_is_blocked(self) -> None:
        decision = self.routing.decide(CallRequest(caller_number="070-0000-0001"))
        self.assertEqual(decision.kind, RouteKind.SPAM_BLOCKED)
        self.assertIsNone(decision.target)

    def test_suspicious_spam_is_sent_to_review(self) -> None:
        decision = self.routing.decide(
            CallRequest(caller_number="070-9999-9999", purpose="대출 광고입니다")
        )
        self.assertEqual(decision.kind, RouteKind.SPAM_REVIEW)

    def test_no_answer_creates_callback_and_notification(self) -> None:
        service = CallService(
            routing=self.routing,
            telephony=DummyTelephonyAdapter(answer_transfer=False),
            notification=DummyNotificationAdapter(),
            voice=DummyVoiceAdapter(),
        )
        outcome = service.handle(
            CallRequest(
                caller_number="02-555-1001",
                caller_name="김고객",
                company_name="가온상사",
                purpose="부가세 신고 문의",
            )
        )
        self.assertEqual(outcome.transfer_status, "no_answer")
        self.assertTrue(outcome.callback_created)
        self.assertIn("홍길원", outcome.notification)

    def test_typed_utterance_finds_company_name_and_employee(self) -> None:
        parsed = TypedUtteranceParser(self.config).parse(
            "010-7777-7777",
            "누리기획 김누리입니다. 홍길육 담당자 바꿔주세요.",
        )
        self.assertEqual(parsed.matched_company, "누리기획")
        self.assertEqual(parsed.call.caller_name, "김누리")
        self.assertEqual(parsed.matched_employee, "홍길육")
        decision = self.routing.decide(parsed.call)
        self.assertEqual(decision.target.name, "홍길육")

    def test_typed_utterance_can_request_owner(self) -> None:
        parsed = TypedUtteranceParser(self.config).parse(
            "010-7777-7777",
            "해든학원 박고객입니다. 대표님과 통화하고 싶습니다.",
        )
        decision = self.routing.decide(parsed.call)
        self.assertEqual(decision.kind, RouteKind.OWNER_REQUEST)
        self.assertEqual(decision.target.name, "홍사장")

    def test_typed_utterance_supports_configured_recognition_alias(self) -> None:
        parsed = TypedUtteranceParser(self.config).parse(
            "010-7777-7777",
            "홀길육 바꿔주세요.",
        )
        decision = self.routing.decide(parsed.call)
        self.assertEqual(decision.target.name, "홍길육")

    def test_registered_number_supplies_company_but_still_needs_caller_name(self) -> None:
        parsed = TypedUtteranceParser(self.config).parse(
            "02-555-1001",
            "홍길삼 과장 바꿔주세요.",
        )
        self.assertEqual(parsed.call.company_name, "가온상사")
        self.assertIsNone(parsed.call.caller_name)

    def test_short_slot_answers_are_extracted(self) -> None:
        parser = TypedUtteranceParser(self.config)
        self.assertEqual(parser.company_from_answer("새봄의원입니다."), "새봄의원")
        self.assertEqual(parser.company_from_answer("처음상사입니다."), "처음상사")
        self.assertEqual(parser.caller_name_from_answer("저는 김철수입니다."), "김철수")


if __name__ == "__main__":
    unittest.main()
