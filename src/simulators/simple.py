"""简单指令模拟器模块"""

from typing import Tuple
from .base import BaseInstructionSimulator, ExecutionResult


class SimpleInstructionSimulator(BaseInstructionSimulator):
    """简单指令模拟器"""

    allowed_keywords = {}  # 不允许任何关键字

    def _is_valid_parts(
        self, left_modifier: str, left_str: str, right_modifier: str, right_str: str
    ) -> bool:
        return (
            left_modifier == ""
            and right_modifier == ""
            and all(ord(c) < 128 for c in left_str + right_str)
        )

    def _match_left(
        self, current_str: str, left_modifier: str, left_str: str
    ) -> Tuple[bool, str]:
        if left_str == "":
            return True, current_str
        if left_str in current_str:
            idx = current_str.find(left_str)
            return True, current_str[:idx] + current_str[idx + len(left_str) :]
        return False, current_str

    def _handle_right(
        self, matched_str: str, right_modifier: str, right_str: str
    ) -> ExecutionResult:
        if not matched_str:  # 空字符串特殊处理
            return ExecutionResult(executed=True, output=right_str + matched_str)
        return ExecutionResult(executed=True, output=matched_str + right_str)
