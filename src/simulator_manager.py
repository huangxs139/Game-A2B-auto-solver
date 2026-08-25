from typing import Dict, List, Type, Tuple, Optional
from pathlib import Path
from dataclasses import dataclass
import re
import json

from src.instruction_simulator import (
    BaseInstructionSimulator,
    SimpleInstructionSimulator,
    ExtendedInstructionSimulator,
    AdvancedInstructionSimulator,
    OnceTrackingSimulator,
)


def get_repo_root() -> Path:
    """获取仓库根目录"""
    return Path(__file__).parent.parent


@dataclass
class TestCase:
    """单个测试样例"""

    input_str: str
    expected_output: str


@dataclass
class TestScenario:
    """测试场景，包含多个测试样例"""

    id: int  # 场景ID
    test_cases: List[TestCase]

    @classmethod
    def from_file(cls, file_path: Path) -> "TestScenario":
        """从.a2b文件加载测试场景

        文件格式示例：
        {
            "input": ["input1", "input2", ...],
            "output": ["output1", "output2", ...]
        }
        """
        # 从文件名解析场景ID
        match = re.match(r"c\d+_(\d+)_.*\.a2b", file_path.name)
        if not match:
            raise ValueError(f"无效的测试文件名: {file_path.name}")
        scenario_id = int(match.group(1))

        # 读取JSON文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 验证数据格式
        if not isinstance(data, dict) or "input" not in data or "output" not in data:
            raise ValueError(f"文件格式错误: {file_path.name}")
        if len(data["input"]) != len(data["output"]):
            raise ValueError(f"输入输出数量不匹配: {file_path.name}")

        # 创建测试样例列表
        test_cases = [
            TestCase(input_str=inp.strip(), expected_output=out.strip())
            for inp, out in zip(data["input"], data["output"])
        ]

        return cls(scenario_id, test_cases)


@dataclass
class TestResult:
    """单个程序的测试结果"""

    scenario_id: int
    program: str
    case_results: List[Tuple[TestCase, int]]  # (测试样例, 状态码)

    @property
    def is_success(self) -> bool:
        """检查是否所有测试样例都通过"""
        return all(status == 0 for _, status in self.case_results)

    def __str__(self) -> str:
        status_desc = {0: "成功", 1: "程序格式错误", 2: "输出不匹配"}

        lines = [f"场景 {self.scenario_id} 测试结果:"]
        lines.append(f"程序:\n{self.program}")
        for test_case, status in self.case_results:
            lines.append(
                f"输入: {test_case.input_str}\n"
                f"期望: {test_case.expected_output}\n"
                f"状态: {status_desc.get(status, '未知错误')}"
            )
        return "\n".join(lines)


class SimulatorManager:
    """模拟器管理类"""

    def __init__(self, test_data_dir: Optional[str] = None):
        self.simulators: Dict[int, Type[BaseInstructionSimulator]] = {
            1: SimpleInstructionSimulator,
            2: ExtendedInstructionSimulator,
            3: AdvancedInstructionSimulator,
            4: OnceTrackingSimulator,
            5: OnceTrackingSimulator,  # 与4相同
            6: SimpleInstructionSimulator,  # 与1相同
        }
        if test_data_dir is None:
            self.test_data_dir = get_repo_root() / "test_data"
        else:
            self.test_data_dir = Path(test_data_dir)

    def load_scenario(self, version: int, scenario_id: int) -> TestScenario:
        """加载指定版本和ID的测试场景"""
        pattern = f"c{version}_{scenario_id}_*.a2b"
        matching_files = list(self.test_data_dir.glob(pattern))

        if not matching_files:
            raise FileNotFoundError(
                f"找不到测试场景文件: version={version}, scenario_id={scenario_id}"
            )
        if len(matching_files) > 1:
            raise ValueError(
                f"找到多个匹配的测试场景文件: {[f.name for f in matching_files]}"
            )

        return TestScenario.from_file(matching_files[0])

    def test_program(self, version: int, scenario_id: int, program: str) -> TestResult:
        """测试单个程序"""
        # 直接加载指定的场景
        scenario = self.load_scenario(version, scenario_id)

        # 创建模拟器实例
        simulator_class = self.simulators.get(version)
        if not simulator_class:
            raise ValueError(f"不支持的模拟器版本: {version}")
        simulator = simulator_class()

        # 运行所有测试样例
        case_results = []
        for test_case in scenario.test_cases:
            status = simulator.validate_and_execute(
                test_case.input_str, test_case.expected_output, program
            )
            case_results.append((test_case, status))

        return TestResult(scenario_id, program, case_results)


def run_test(version: int, scenario_id: int, program: str) -> TestResult:
    """测试入口函数

    Args:
        version: 模拟器版本(1-6)
        scenario_id: 测试场景ID
        program: 要测试的程序

    Returns:
        TestResult: 测试结果对象

    Raises:
        ValueError: 当版本号或场景ID无效时
        FileNotFoundError: 当测试数据文件不存在时
    """
    manager = SimulatorManager()
    return manager.test_program(version, scenario_id, program)
