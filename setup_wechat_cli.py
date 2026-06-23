"""
wechat-cli 一键安装脚本
自动完成 wechat-cli 的安装和配置。

使用方式:
    python setup_wechat_cli.py

支持环境:
    - Windows (主要测试环境)
    - macOS / Linux (部分支持)

安装内容:
    1. 检查 Python 环境
    2. 克隆 wechat-cli 源码 (或指定本地路径)
    3. 创建独立虚拟环境
    4. 安装依赖
    5. 创建全局启动入口 wechat-cli.bat
    6. 配置 PATH (可选)
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

# ============ 配置区 ============
WECHAT_CLI_REPO = "https://github.com/huohuoer/wechat-cli.git"
INSTALL_DIR = Path.home() / "tools" / "wechat-cli"
VENV_DIR = INSTALL_DIR / "venv"
ENTRY_DIR = Path.home() / "bin"  # 已在 PATH 中的目录
ENTRY_SCRIPT = ENTRY_DIR / "wechat-cli.bat"
PYTHON_EXE = sys.executable  # 使用当前 Python
# ============ 配置区结束 ============


def run_cmd(cmd, cwd=None, check=True):
    """运行命令并返回输出"""
    print(f"[执行] {cmd}")
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=cwd,
        capture_output=True,
        text=True
    )
    if check and result.returncode != 0:
        print(f"[错误] 命令执行失败: {cmd}")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        sys.exit(1)
    return result


def check_python():
    """检查 Python 版本"""
    print("\n[1/6] 检查 Python 环境...")
    version = sys.version_info
    if version < (3, 8):
        print(f"[错误] Python 版本过低: {version.major}.{version.minor}")
        print("需要 Python 3.8 或更高版本")
        sys.exit(1)
    print(f"  ✓ Python {version.major}.{version.minor}.{version.micro}")
    print(f"  路径: {PYTHON_EXE}")


def clone_or_update_repo():
    """克隆或更新 wechat-cli 仓库"""
    print(f"\n[2/6] 准备 wechat-cli 源码...")
    
    if INSTALL_DIR.exists():
        print(f"  目录已存在: {INSTALL_DIR}")
        answer = input("  是否更新现有仓库? [y/N]: ")
        if answer.lower() == 'y':
            run_cmd("git pull", cwd=INSTALL_DIR)
            print("  ✓ 仓库已更新")
        else:
            print("  ✓ 使用现有仓库")
        return
    
    # 克隆仓库
    print(f"  克隆仓库到: {INSTALL_DIR}")
    run_cmd(f"git clone {WECHAT_CLI_REPO} {INSTALL_DIR}")
    print("  ✓ 仓库克隆完成")


def create_venv():
    """创建虚拟环境"""
    print(f"\n[3/6] 创建虚拟环境...")
    
    if VENV_DIR.exists():
        print(f"  虚拟环境已存在: {VENV_DIR}")
        answer = input("  是否重新创建? [y/N]: ")
        if answer.lower() == 'y':
            shutil.rmtree(VENV_DIR)
        else:
            print("  ✓ 使用现有虚拟环境")
            return
    
    run_cmd(f'"{PYTHON_EXE}" -m venv {VENV_DIR}')
    print(f"  ✓ 虚拟环境创建完成: {VENV_DIR}")


def install_dependencies():
    """安装依赖"""
    print(f"\n[4/6] 安装依赖...")
    
    pip_exe = VENV_DIR / "Scripts" / "pip.exe"
    if not pip_exe.exists():
        pip_exe = VENV_DIR / "bin" / "pip"  # macOS/Linux
    
    requirements = INSTALL_DIR / "requirements.txt"
    if requirements.exists():
        run_cmd(f'"{pip_exe}" install -r {requirements}')
        print("  ✓ 依赖安装完成 (from requirements.txt)")
    else:
        # 尝试安装 wechat-cli 本身
        run_cmd(f'"{pip_exe}" install -e {INSTALL_DIR}')
        print("  ✓ wechat-cli 安装完成 (editable mode)")


def create_entry_script():
    """创建全局启动入口"""
    print(f"\n[5/6] 创建全局启动入口...")
    
    # 确保入口目录存在
    ENTRY_DIR.mkdir(parents=True, exist_ok=True)
    
    # 确定虚拟环境中的 wechat-cli 可执行文件
    venv_bin = VENV_DIR / "Scripts" if os.name == "nt" else VENV_DIR / "bin"
    wechat_cli_exe = venv_bin / "wechat-cli.exe"
    if not wechat_cli_exe.exists():
        wechat_cli_exe = venv_bin / "wechat-cli"  # macOS/Linux
    
    if os.name == "nt":
        # Windows: 创建 .bat 文件
        bat_content = f"""@echo off
"{wechat_cli_exe}" %*
"""
        ENTRY_SCRIPT.write_text(bat_content, encoding="utf-8")
        print(f"  ✓ 入口脚本已创建: {ENTRY_SCRIPT}")
    else:
        # macOS/Linux: 创建可执行脚本
        sh_content = f"""#!/bin/bash
"{wechat_cli_exe}" "$@"
"""
        ENTRY_SCRIPT.write_text(sh_content, encoding="utf-8")
        ENTRY_SCRIPT.chmod(0o755)
        print(f"  ✓ 入口脚本已创建: {ENTRY_SCRIPT}")
    
    # 检查 PATH
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    if str(ENTRY_DIR) not in path_dirs:
        print(f"\n  [提醒] {ENTRY_DIR} 不在 PATH 中")
        print(f"  请手动添加以下内容到环境变量 PATH:")
        print(f"    {ENTRY_DIR}")
        
        if os.name == "nt":
            print(f"\n  或运行以下命令 (需要管理员权限):")
            print(f'    setx PATH "%PATH%;{ENTRY_DIR}"')
    else:
        print(f"  ✓ {ENTRY_DIR} 已在 PATH 中")


def verify_installation():
    """验证安装"""
    print(f"\n[6/6] 验证安装...")
    
    try:
        result = subprocess.run(
            "wechat-cli --version",
            shell=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"  ✓ wechat-cli 安装成功!")
            print(f"  版本: {result.stdout.strip()}")
        else:
            print(f"  [警告] wechat-cli 命令可用，但返回非零退出码")
    except FileNotFoundError:
        print(f"  [警告] wechat-cli 命令未找到")
        print(f"  请确保 {ENTRY_DIR} 在 PATH 中，或重新打开终端")
    except Exception as e:
        print(f"  [警告] 验证失败: {e}")


def main():
    print("=" * 60)
    print("wechat-cli 一键安装脚本")
    print("=" * 60)
    
    # 检查操作系统
    if os.name != "nt":
        print(f"\n[提醒] 当前系统: {os.name}")
        print("本脚本主要针对 Windows 测试，macOS/Linux 可能需要手动调整")
        answer = input("是否继续? [y/N]: ")
        if answer.lower() != 'y':
            sys.exit(0)
    
    # 执行安装步骤
    check_python()
    clone_or_update_repo()
    create_venv()
    install_dependencies()
    create_entry_script()
    verify_installation()
    
    print("\n" + "=" * 60)
    print("安装完成!")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 确保微信 PC 版正在运行且已登录")
    print("  2. 在 AI 助手中说: '生成今天的微信摘要'")
    print("  3. 或手动测试: wechat-cli --help")
    print()


if __name__ == "__main__":
    main()
