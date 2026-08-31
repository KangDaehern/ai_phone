from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import CallRequest, Employee, RouteDecision


class TelephonyAdapter(Protocol):
    def transfer(self, employee: Employee, timeout_seconds: int) -> bool: ...

    def reject(self, reason: str) -> None: ...


class NotificationAdapter(Protocol):
    def send_call_summary(self, employee: Employee, message: str) -> str: ...

    def send_spam_review(self, employee: Employee, call: CallRequest, reason: str) -> str: ...


class VoiceAdapter(Protocol):
    def announce_to_employee(self, employee: Employee, message: str) -> None: ...

    def unavailable_message(self, employee: Employee | None) -> str: ...


@dataclass
class DummyTelephonyAdapter:
    answer_transfer: bool = True

    def transfer(self, employee: Employee, timeout_seconds: int) -> bool:
        print(f"[DUMMY PBX] 내선 {employee.extension} {employee.name}에게 연결 ({timeout_seconds}초 대기)")
        return self.answer_transfer

    def reject(self, reason: str) -> None:
        print(f"[DUMMY PBX] 통화 차단: {reason}")


class DummyNotificationAdapter:
    def send_call_summary(self, employee: Employee, message: str) -> str:
        result = f"[DUMMY 알림톡 → {employee.name}] {message}"
        print(result)
        return result

    def send_spam_review(self, employee: Employee, call: CallRequest, reason: str) -> str:
        result = (
            f"[DUMMY 스팸 검토 알림톡 → {employee.name}] "
            f"발신번호={call.caller_number}, 사유={reason}, 용건={call.purpose or '미확인'}"
        )
        print(result)
        return result


class DummyVoiceAdapter:
    def announce_to_employee(self, employee: Employee, message: str) -> None:
        print(f"[DUMMY 음성 사전안내 → {employee.name}] {message}")

    def unavailable_message(self, employee: Employee | None) -> str:
        target = employee.name if employee else "담당자"
        message = f"{target}님이 지금 전화를 받기 어렵습니다. 메모를 남겨주시면 전달하겠습니다."
        print(f"[DUMMY 음성 → 고객] {message}")
        return message


# 실제 연동 시 아래 구현체를 추가한다.
# - OpenAIRealtimeVoiceAdapter: Realtime API의 SIP 수신/음성 대화/통화 전환 연동
# - CarrierSipTelephonyAdapter: 통신사 SIP 트렁크 또는 PBX API 연동
# - KakaoAlimtalkNotificationAdapter: 계약한 공식 딜러의 알림톡 API 연동

