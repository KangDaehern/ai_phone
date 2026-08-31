from __future__ import annotations

import os
import subprocess
import sys


class WindowsSpeechSynthesizer:
    """Windows System.Speech를 이용하는 로컬 TTS.

    텍스트는 PowerShell 명령행에 삽입하지 않고 표준 입력으로 전달한다.
    """

    def __init__(self, voice_name: str = "Microsoft Heami Desktop", rate: int = 1, volume: int = 100):
        self.voice_name = voice_name
        self.rate = max(-10, min(10, rate))
        self.volume = max(0, min(100, volume))

    @staticmethod
    def is_supported() -> bool:
        return os.name == "nt"

    def speak(self, text: str) -> None:
        print(f"[AI 음성] {text}")
        if not self.is_supported():
            return
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false); "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$voice = $env:AI_PHONE_TTS_VOICE; "
            "if ($voice) { $s.SelectVoice($voice) }; "
            "$s.Rate = [int]$env:AI_PHONE_TTS_RATE; "
            "$s.Volume = [int]$env:AI_PHONE_TTS_VOLUME; "
            "$text = [Console]::In.ReadToEnd(); "
            "$s.Speak($text)"
        )
        environment = os.environ.copy()
        environment.update(
            {
                "AI_PHONE_TTS_VOICE": self.voice_name,
                "AI_PHONE_TTS_RATE": str(self.rate),
                "AI_PHONE_TTS_VOLUME": str(self.volume),
            }
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            input=text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            env=environment,
            creationflags=creation_flags,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip() or "알 수 없는 Windows TTS 오류"
            raise RuntimeError(detail)

    @staticmethod
    def installed_voices() -> list[str]:
        if not WindowsSpeechSynthesizer.is_supported():
            return []
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True,
            encoding="utf-8",
            capture_output=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
        return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


class SilentSpeechSynthesizer:
    def speak(self, text: str) -> None:
        print(f"[AI 음성 비활성] {text}")


def require_utf8_console() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8")
