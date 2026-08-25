"""关键字指令模拟器基类模块"""

from typing import Set, Tuple
from .base import BaseInstructionSimulator


class KeywordInstructionSimulator(BaseInstructionSimulator):
    """支持关键字的指令模拟器基类"""

    KEYWORDS: Set[str] = set()  # 子类需要定义具体的关键字集合

    def _extract_parts(self, s: str) -> Tuple[str, str]:
        s = s.strip()
        if not s.startswith("("):
            return "", s
        end_bracket = s.find(")")
        if end_bracket == -1:
            return "", s
        return s[1:end_bracket], s[end_bracket + 1 :]

    def _is_valid_parts(
        self, left_modifier: str, left_str: str, right_modifier: str, right_str: str
    ) -> bool:
        return (
            (left_modifier == "" or left_modifier in self.KEYWORDS)
            and (right_modifier == "" or right_modifier in self.KEYWORDS)
            and all(ord(c) < 128 for c in left_str + right_str)
        )
