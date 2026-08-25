"""基础指令模拟器模块

提供指令模拟器的基础类和类型定义。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple, NamedTuple, Optional, Dict, List
from enum import Enum, auto, Flag


@dataclass
class ValidationError:
    """程序验证错误类

    用于记录程序验证过程中发现的错误信息。

    Attributes:
        line_number: 错误所在行号
        line_content: 错误所在行的内容
        error_type: 错误类型
        error_message: 错误信息
    """

    line_number: int
    line_content: str
    error_type: str
    error_message: str


class ExecutionStatus(Enum):
    """程序执行状态枚举"""

    SUCCESS = auto()  # 程序合法且输出符合预期
    INVALID_PROGRAM = auto()  # 程序不合法（格式错误）
    WRONG_OUTPUT = auto()  # 程序合法但输出与预期不符


class ExecutionResult(NamedTuple):
    """指令执行结果"""

    executed: bool = False
    output: str = ""
    should_return: bool = False


class InstructionParts(NamedTuple):
    """指令解析结果"""

    left_keyword: Optional[str]
    left_str: str
    right_keyword: Optional[str]
    right_str: str


class KeywordPosition(Flag):
    """关键字允许出现的位置"""

    NONE = 0
    LEFT = auto()
    RIGHT = auto()
    BOTH = LEFT | RIGHT


class BaseInstructionSimulator(ABC):
    """指令模拟器的基类"""

    RESERVED_CHARS = {"=", "#", "(", ")"}
    allowed_keywords: Dict[str, KeywordPosition] = {}  # 子类需要定义具体的关键字集合
    errors: List[ValidationError] = []  # 存储验证过程中产生的错误信息

    def _extract_keyword(self, s: str) -> Tuple[Optional[str], Optional[str]]:
        """从字符串中提取关键字和实际字符串

        Args:
            s: 输入字符串，可能包含(keyword)格式的关键字

        Returns:
            Tuple[Optional[str], Optional[str]]: (关键字, 实际字符串)
                - 关键字为None: 表示不存在keyword字段
                - 关键字为"": 表示存在一个空的keyword
                - 实际字符串为None: 表示输入字符串格式不合法
                - 实际字符串为"": 表示存在一个合法的空字符串
        """
        s = s.strip()
        if not s:
            return None, ""

        # 处理不带关键字的情况
        if not s.startswith("("):
            return (
                (None, None) if any(c in s for c in self.RESERVED_CHARS) else (None, s)
            )

        # 处理带关键字的情况
        end_bracket = s.find(")")
        if end_bracket == -1:  # 找不到右括号
            return None, None

        keyword = s[1:end_bracket]
        remaining = s[end_bracket + 1 :].strip()

        # 检查关键字和剩余字符串中是否包含保留字符
        if any(c in self.RESERVED_CHARS for c in keyword + remaining):
            return None, None

        return keyword, remaining

    def _parse_instruction(self, instruction: str) -> Optional[InstructionParts]:
        """解析指令字符串

        Args:
            instruction: 指令字符串

        Returns:
            Optional[InstructionParts]: 解析结果，如果格式不合法则返回None
        """
        # 快速检查基本格式
        if instruction.count("=") != 1:
            if instruction.count("=") == 0:
                self.errors.append(
                    ValidationError(1, instruction, "INVALID_FORMAT", "缺少等号")
                )
            elif instruction.count("=") > 1:
                self.errors.append(
                    ValidationError(1, instruction, "INVALID_FORMAT", "等号数量超过1个")
                )
        if not all(ord(c) < 128 for c in instruction):
            self.errors.append(
                ValidationError(1, instruction, "INVALID_FORMAT", "包含非ASCII字符")
            )

        # 如果有错误,直接返回错误信息
        if self.errors:
            return None

        # 分割并提取关键字
        left, right = instruction.split("=")
        left_keyword, left_str = self._extract_keyword(left)
        right_keyword, right_str = self._extract_keyword(right)

        return InstructionParts(
            left_keyword=left_keyword,
            left_str=left_str,
            right_keyword=right_keyword,
            right_str=right_str,
        )

    def _is_valid_parts(
        self,
        left_keyword: Optional[str],
        left_str: str,
        right_keyword: Optional[str],
        right_str: str,
    ) -> bool:
        """验证指令各部分是否符合当前模拟器的规则"""
        # 检查左侧关键字
        if left_keyword is not None:  # 存在关键字（可能为空）
            if left_keyword not in self.allowed_keywords:
                return False
            if not (self.allowed_keywords[left_keyword] & KeywordPosition.LEFT):
                return False

        # 检查右侧关键字
        if right_keyword is not None:  # 存在关键字（可能为空）
            if right_keyword not in self.allowed_keywords:
                return False
            if not (self.allowed_keywords[right_keyword] & KeywordPosition.RIGHT):
                return False

        return True

    @abstractmethod
    def _match_left(
        self, current_str: str, left_keyword: str, left_str: str
    ) -> Tuple[bool, str]:
        """检查左侧是否匹配并返回处理后的字符串"""

    @abstractmethod
    def _handle_right(
        self, matched_str: str, right_keyword: str, right_str: str
    ) -> ExecutionResult:
        """根据右侧规则处理字符串"""

    def execute_instruction(
        self, current_str: str, instruction: str
    ) -> ExecutionResult:
        """统一的指令执行流程"""
        # 解析指令
        parts = self._parse_instruction(instruction)
        if parts is None:
            return ExecutionResult(executed=False, output=current_str)

        # 验证指令是否符合当前模拟器的规则
        if not self._is_valid_parts(
            parts.left_keyword, parts.left_str, parts.right_keyword, parts.right_str
        ):
            return ExecutionResult(executed=False, output=current_str)

        # 执行指令
        matched, matched_str = self._match_left(
            current_str, parts.left_keyword, parts.left_str
        )
        if not matched:
            return ExecutionResult(executed=False, output=current_str)

        return self._handle_right(matched_str, parts.right_keyword, parts.right_str)

    def is_valid_program(self, program: str) -> bool:
        """验证程序是否合法"""
        for line_number, line in enumerate(program.strip().split("\n"), start=1):
            line = line.split("#")[0].strip()
            if not line:
                self.errors.append(
                    ValidationError(
                        line_number,
                        line,
                        "EMPTY_LINE",
                        "当前行没有可执行的指令，仅包含注释或空白字符",
                    )
                )
                continue

            parts = self._parse_instruction(line)
            if parts is None:
                return False

            if not self._is_valid_parts(
                parts.left_keyword, parts.left_str, parts.right_keyword, parts.right_str
            ):
                return False

        return True

    def execute_program(self, input_str: str, program: str) -> str:
        """执行程序"""
        current_str = input_str
        program_lines = program.strip().split("\n")

        executed = True
        while executed:
            executed = False
            for line in program_lines:
                line = line.split("#")[0].strip()
                if not line:
                    continue

                result = self.execute_instruction(current_str, line)
                if result.executed:
                    current_str = result.output
                    executed = True
                    if result.should_return:
                        return current_str
                    break

        return current_str

    def validate_and_execute(
        self, input_str: str, expected_output: str, program: str
    ) -> Tuple[ExecutionStatus, str]:
        """验证并执行程序"""
        if not self.is_valid_program(program):
            return ExecutionStatus.INVALID_PROGRAM, self.get_formatted_errors()

        try:
            actual_output = self.execute_program(input_str, program)
        except Exception as e:
            print(f"执行程序时出错: {e}")
            return ExecutionStatus.INVALID_PROGRAM, self.get_formatted_errors()

        return (
            ExecutionStatus.SUCCESS,
            (
                self.get_formatted_errors()
                if actual_output == expected_output
                else ExecutionStatus.WRONG_OUTPUT
            ),
            self.get_formatted_errors(),
        )

    def get_formatted_errors(self) -> str:
        """将错误信息格式化为可读的字符串

        Returns:
            str: 格式化后的错误信息字符串,包含每个错误的行号、错误类型、错误信息和原始代码行
        """
        ret_str = ""
        for error in self.errors:
            ret_str += (
                f"在第{error.line_number}行发生{error.error_type}错误："
                f"{error.message}。该行原文为'{error.line}'\n"
            )
        return ret_str
