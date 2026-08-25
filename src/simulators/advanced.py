"""高级指令模拟器模块"""

from typing import Tuple
from .keyword_base import KeywordInstructionSimulator
from .base import ExecutionResult, BaseInstructionSimulator, KeywordPosition


class AdvancedInstructionSimulator(KeywordInstructionSimulator):
    """支持start和end关键字的指令模拟器"""

    KEYWORDS = {"start", "end", "return"}
    allowed_keywords = {
        "start": KeywordPosition.BOTH,  # start 可以出现在两侧
        "end": KeywordPosition.BOTH,  # end 可以出现在两侧
        "return": KeywordPosition.RIGHT,  # return 只能出现在右侧
    }

    def _match_left(
        self, current_str: str, left_modifier: str, left_str: str
    ) -> Tuple[bool, str]:
        if left_modifier == "start" and current_str.startswith(left_str):
            return True, current_str[len(left_str) :]
        elif left_modifier == "end" and current_str.endswith(left_str):
            return True, current_str[: -len(left_str)]
        elif left_str in current_str:
            idx = current_str.find(left_str)
            return True, current_str[:idx] + current_str[idx + len(left_str) :]
        return False, current_str

    def _handle_right(
        self, matched_str: str, right_modifier: str, right_str: str
    ) -> ExecutionResult:
        if right_modifier == "return":
            return ExecutionResult(executed=True, output=right_str, should_return=True)
        elif right_modifier == "start":
            return ExecutionResult(executed=True, output=right_str + matched_str)
        elif right_modifier == "end":
            return ExecutionResult(executed=True, output=matched_str + right_str)
        return ExecutionResult(executed=True, output=matched_str + right_str)
