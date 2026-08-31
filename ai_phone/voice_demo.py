from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from .config import load_office_config
from .conversation import TypedUtteranceParser
from .models import RouteKind
from .routing import RoutingEngine
from .tts import SilentSpeechSynthesizer, WindowsSpeechSynthesizer, require_utf8_console


def default_config_path() -> Path:
    return Path(__file__).resolve().parents[1] / "config" / "office.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="키보드 입력 + Windows 스피커 AI 전화 데모")
    parser.add_argument("--config", type=Path, default=default_config_path())
    parser.add_argument("--caller", default="010-7777-7777", help="더미 발신번호")
    parser.add_argument("--voice", default="Microsoft Heami Desktop", help="Windows TTS 음성 이름")
    parser.add_argument("--rate", type=int, default=-1, help="음성 속도 -10~10 (기본값 -1)")
    parser.add_argument("--no-audio", action="store_true", help="스피커 출력 없이 텍스트만 표시")
    parser.add_argument("--simulate-no-answer", action="store_true", help="담당자 무응답 상황")
    parser.add_argument("--list-voices", action="store_true", help="설치된 Windows 음성 목록")
    return parser


def main() -> None:
    require_utf8_console()
    args = build_parser().parse_args()
    if args.list_voices:
        for voice in WindowsSpeechSynthesizer.installed_voices():
            print(voice)
        return

    config = load_office_config(args.config)
    routing = RoutingEngine(config)
    utterance_parser = TypedUtteranceParser(config)
    speaker = (
        SilentSpeechSynthesizer()
        if args.no_audio
        else WindowsSpeechSynthesizer(voice_name=args.voice, rate=args.rate)
    )

    speaker.speak(
        f"안녕하세요. {config.office.name}입니다. "
        "업체명과 성함, 찾으시는 담당자나 용건을 말씀해 주세요."
    )
    print("\n마이크 대신 고객이 말할 문장을 입력하세요.")
    print("예: 누리기획 김누리입니다. 홍길육 담당자 바꿔주세요.")
    print("예: 해든학원 박고객입니다. 대표님과 통화하고 싶습니다.")
    utterance = input("\n[고객 입력] ").strip()
    if not utterance:
        speaker.speak("말씀하신 내용을 확인하지 못했습니다. 다시 전화해 주세요.")
        return

    parsed = utterance_parser.parse(args.caller, utterance)
    call = parsed.call

    if not call.company_name and not call.caller_name:
        speaker.speak("네. 연결해 드리기 전에, 어느 업체의 누구신지 말씀해 주시겠어요?")
        identity_answer = input("[고객 입력] ").strip()
        identity = utterance_parser.parse(args.caller, identity_answer)
        call = replace(
            call,
            company_name=identity.call.company_name,
            caller_name=identity.call.caller_name,
        )

    if not call.company_name:
        speaker.speak("죄송하지만 업체명을 다시 한번 말씀해 주세요.")
        company_answer = input("[고객 입력] ").strip()
        call = replace(call, company_name=utterance_parser.company_from_answer(company_answer))

    if not call.caller_name:
        speaker.speak("전화 주신 분의 성함도 말씀해 주세요.")
        name_answer = input("[고객 입력] ").strip()
        call = replace(call, caller_name=utterance_parser.caller_name_from_answer(name_answer))

    if not call.company_name or not call.caller_name:
        speaker.speak(
            "죄송합니다. 업체명과 성함을 정확히 확인하지 못했습니다. "
            "대표번호로 다시 전화해 주시거나 잠시 후 다시 시도해 주세요."
        )
        print("[연결 중단] 업체명과 성함 확인 실패")
        return

    parsed = replace(
        parsed,
        call=call,
        matched_company=call.company_name,
    )
    decision = routing.decide(call)
    print(
        f"[인식 결과] 업체={parsed.matched_company or '미확인'}, "
        f"성함={parsed.call.caller_name or '미확인'}, "
        f"요청 직원={parsed.matched_employee or '미확인'}"
    )
    print(f"[라우팅 판단] {decision.reason} / 신뢰도={decision.confidence:.2f}")

    if decision.kind in {RouteKind.SPAM_BLOCKED, RouteKind.SPAM_REVIEW}:
        speaker.speak("죄송합니다. 이 전화는 담당 직원에게 연결해 드릴 수 없습니다.")
        print(f"[DUMMY 알림톡] {routing.spam_reviewer.name}에게 스팸 검토 알림 전송")
        return

    if not decision.target:
        speaker.speak("현재 연결 가능한 담당자가 없습니다. 메모를 남겨주시면 전달하겠습니다.")
        return

    speaker.speak(f"네, 확인했습니다. {decision.target.name} 담당자에게 연결해 드릴게요. 잠시만 기다려 주세요.")
    print(
        f"[DUMMY 담당자 사전안내 → 내선 {decision.target.extension}] "
        f"{decision.preconnect_announcement}"
    )
    print(
        f"[DUMMY PBX] 내선 {decision.target.extension} {decision.target.name}에게 연결, "
        f"{config.office.ring_timeout_seconds}초 대기"
    )

    if args.simulate_no_answer:
        speaker.speak(
            f"죄송합니다. {decision.target.name} 담당자가 지금 전화를 받기 어렵습니다. "
            "말씀하신 내용과 연락처를 전달하겠습니다."
        )
        print(
            f"[DUMMY 알림톡 → {decision.target.name}] "
            f"부재중 전화 / {parsed.matched_company or '업체 미확인'} / "
            f"{parsed.call.caller_name or '성함 미확인'} / {args.caller} / {utterance}"
        )
    else:
        speaker.speak("담당자에게 연결되었습니다.")


if __name__ == "__main__":
    main()
