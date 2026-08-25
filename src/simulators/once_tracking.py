"""支持once关键字的指令模拟器模块"""

from .advanced import AdvancedInstructionSimulator
from .base import KeywordPosition


class OnceTrackingSimulator(AdvancedInstructionSimulator):
    """支持once关键字的指令模拟器"""

    allowed_keywords = {
        **AdvancedInstructionSimulator.allowed_keywords,  # 继承父类的关键字
        "once": KeywordPosition.LEFT,  # once 只能出现在左侧
    }

    KEYWORDS = {"start", "end", "return", "once"}

    def execute_program(self, input_str: str, program: str) -> str:
        """重写执行程序方法以支持once功能"""
        current_str = input_str
        program_lines = program.strip().split("\n")

        while True:
            executed = False
            i = 0
            while i < len(program_lines):
                line = program_lines[i].split("#")[0].strip()
                if not line:
                    i += 1
                    continue

                result = self.execute_instruction(current_str, line)
                if result.executed:
                    current_str = result.output
                    executed = True

                    # 处理once指令
                    left = line.split("=")[0].strip()
                    if left.startswith("(once)"):
                        program_lines.pop(i)
                        i -= 1

                    if result.should_return:
                        return current_str
                    break
                i += 1

            if not executed:
                break

        return current_str
