from pathlib import Path
import os
import re


def is_valid_filename(filename: str) -> bool:
    """检查文件名是否符合cx_y_zzz.a2b格式

    Args:
        filename: 文件名

    Returns:
        bool: 是否符合格式
    """
    # 检查后缀名
    if not filename.endswith(".a2b"):
        return False

    # 去掉后缀名后检查主文件名格式
    basename = filename[:-4]  # 移除.a2b
    pattern = r"^c\d+_\d+_.*$"  # 匹配cx_y_zzz格式
    return bool(re.match(pattern, basename))


def get_repo_root() -> Path:
    """获取仓库根目录"""
    return Path(__file__).parent.parent


def clean_test_data():
    """清理test_data文件夹，只保留符合命名规范的.a2b文件"""
    # 使用repo根目录
    test_data_dir = get_repo_root() / "test_data"

    # 检查路径是否存在
    print(f"检查路径: {test_data_dir}")
    if not os.path.exists(test_data_dir):
        print("错误: test_data文件夹不存在")
        return

    # 尝试列出目录内容
    try:
        print("\n当前文件夹内容:")
        files = os.listdir(test_data_dir)
        print(f"找到的文件: {files}")

        # 删除不符合要求的文件
        for file in files:
            if not is_valid_filename(file):
                full_path = test_data_dir / file
                try:
                    os.remove(full_path)
                    print(f"已删除: {file} (不符合命名规范)")
                except Exception as e:
                    print(f"删除 {file} 时出错: {str(e)}")
            else:
                print(f"保留: {file} (符合命名规范)")

        # 显示清理后的内容
        print("\n清理后的文件:")
        remaining_files = os.listdir(test_data_dir)
        print(f"剩余文件: {remaining_files}")
        print(f"共保留 {len(remaining_files)} 个文件")

    except Exception as e:
        print(f"访问目录时出错: {str(e)}")


if __name__ == "__main__":
    clean_test_data()
