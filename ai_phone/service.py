from __future__ import annotations

from .adapters import NotificationAdapter, TelephonyAdapter, VoiceAdapter
from .models import CallOutcome, CallRequest, RouteKind
from .routing import RoutingEngine


class CallService:
    def __init__(
        self,
        routing: RoutingEngine,
        telephony: TelephonyAdapter,
        notification: NotificationAdapter,
        voice: VoiceAdapter,
    ):
        self.routing = routing
        self.telephony = telephony
        self.notification = notification
        self.voice = voice

    def handle(self, call: CallRequest) -> CallOutcome:
        decision = self.routing.decide(call)
        reviewer = self.routing.spam_reviewer

        if decision.kind == RouteKind.SPAM_BLOCKED:
            self.telephony.reject(decision.reason)
            notification = self.notification.send_spam_review(reviewer, call, decision.reason)
            return CallOutcome(decision, "blocked", False, "스팸 전화가 차단되었습니다.", notification)

        if decision.kind == RouteKind.SPAM_REVIEW:
            self.telephony.reject(decision.reason)
            notification = self.notification.send_spam_review(reviewer, call, decision.reason)
            return CallOutcome(decision, "spam_review", False, "검토 대상 전화로 분류되었습니다.", notification)

        if not decision.target:
            message = self.voice.unavailable_message(decision.original_target)
            return CallOutcome(decision, "unavailable", True, message, None)

        if decision.preconnect_announcement:
            self.voice.announce_to_employee(decision.target, decision.preconnect_announcement)

        answered = self.telephony.transfer(
            decision.target,
            self.routing.config.office.ring_timeout_seconds,
        )
        if answered:
            return CallOutcome(decision, "connected", False, "담당자에게 연결되었습니다.", None)

        message = self.voice.unavailable_message(decision.target)
        summary = (
            f"부재중 전화: {call.company_name or (decision.company.name if decision.company else '업체 미확인')} / "
            f"{call.caller_name or '성함 미확인'} / {call.purpose or '용건 미확인'} / "
            f"{call.caller_number}"
        )
        notification = self.notification.send_call_summary(decision.target, summary)
        return CallOutcome(decision, "no_answer", True, message, notification)

