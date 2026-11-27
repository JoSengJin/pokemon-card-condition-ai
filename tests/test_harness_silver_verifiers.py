"""교차 검증 시험용 주입 함수(시험 없음): 고정 값을 내는 함수, 항상 실패하는 함수, 받은 입력을 기록하는 함수."""


def answer(value):
    """항상 value를 내는 판정 함수."""
    def verifier(probe):
        return value
    return verifier


def boom(probe):
    """항상 오류를 내는 판정 함수."""
    raise RuntimeError("verifier down")


def recorder(seen, value):
    """받은 입력을 seen에 쌓고 value를 내는 판정 함수."""
    def verifier(probe):
        seen.append(probe)
        return value
    return verifier
