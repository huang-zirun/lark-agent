#!/usr/bin/env python3
"""
DevFlow Engine 统一启动脚本
用于同时启动前端和后端服务

使用方法：

# 启动前后端（默认配置）
python server.py

# 指定端口
python server.py --backend-port 8080 --frontend-port 3000

# 只启动后端
python server.py --no-frontend

# 只启动前端
python server.py --no-backend

# 查看帮助
python server.py --help
"""

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional


# 颜色代码（用于日志输出）
class Colors:
    SERVER = "\033[36m"  # 青色
    BACKEND = "\033[34m"  # 蓝色
    FRONTEND = "\033[35m"  # 紫色
    WARNING = "\033[33m"  # 黄色
    ERROR = "\033[31m"  # 红色
    RESET = "\033[0m"  # 重置


class ServerManager:
    """服务管理器，负责启动和管理前后端进程"""

    def __init__(
        self,
        backend_port: int = 19999,
        frontend_port: int = 3000,
        backend_host: str = "127.0.0.1",
        frontend_host: str = "127.0.0.1",
        enable_backend: bool = True,
        enable_frontend: bool = True,
    ):
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.backend_host = backend_host
        self.frontend_host = frontend_host
        self.enable_backend = enable_backend
        self.enable_frontend = enable_frontend

        self.backend_process: Optional[subprocess.Popen] = None
        self.frontend_process: Optional[subprocess.Popen] = None
        self.shutdown_event = threading.Event()

        # 项目路径
        self.root_dir = Path(__file__).parent.resolve()
        self.backend_dir = self.root_dir / "backend"
        self.frontend_dir = self.root_dir / "frontend"

    def log(self, message: str, source: str = "SERVER"):
        """打印带颜色和时间戳的日志"""
        timestamp = time.strftime("%H:%M:%S")
        color = getattr(Colors, source, Colors.SERVER)
        prefix = f"[{source}]"
        # 处理编码问题，替换无法编码的字符
        try:
            print(f"{color}{prefix}{Colors.RESET} [{timestamp}] {message}")
        except UnicodeEncodeError:
            # 如果打印失败，使用安全编码
            safe_message = message.encode('utf-8', errors='ignore').decode('utf-8')
            print(f"{color}{prefix}{Colors.RESET} [{timestamp}] {safe_message}")

    def check_dependencies(self) -> bool:
        """检查必要的依赖是否已安装"""
        all_ok = True

        if self.enable_backend:
            # 检查 uv
            if not self._command_exists("uv"):
                self.log("错误: 未找到 'uv' 命令。请先安装 uv: https://github.com/astral-sh/uv", "ERROR")
                all_ok = False

        if self.enable_frontend:
            # 检查 npm
            if not self._command_exists("npm"):
                self.log("错误: 未找到 'npm' 命令。请先安装 Node.js: https://nodejs.org/", "ERROR")
                all_ok = False

            # 检查 node_modules
            if not (self.frontend_dir / "node_modules").exists():
                self.log("警告: 前端依赖未安装，正在自动安装...", "WARNING")
                if not self._install_frontend_deps():
                    all_ok = False

        return all_ok

    def _command_exists(self, cmd: str) -> bool:
        """检查命令是否存在"""
        try:
            # Windows 上使用 shell=True 以确保能正确找到 PATH 中的命令
            if sys.platform == "win32":
                result = subprocess.run(
                    f"{cmd} --version",
                    capture_output=True,
                    check=False,
                    shell=True,
                )
            else:
                result = subprocess.run(
                    [cmd, "--version"],
                    capture_output=True,
                    check=False,
                )
            return result.returncode == 0
        except FileNotFoundError:
            return False

    def _install_frontend_deps(self) -> bool:
        """安装前端依赖"""
        try:
            result = subprocess.run(
                ["npm", "install"],
                cwd=self.frontend_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if result.returncode == 0:
                self.log("前端依赖安装成功", "FRONTEND")
                return True
            else:
                self.log(f"前端依赖安装失败: {result.stderr}", "ERROR")
                return False
        except Exception as e:
            self.log(f"前端依赖安装出错: {e}", "ERROR")
            return False

    def start_backend(self):
        """启动后端服务"""
        self.log(f"正在启动后端服务...")
        self.log(f"后端地址: http://{self.backend_host}:{self.backend_port}")

        # 构建启动命令
        cmd = [
            "uv", "run", "uvicorn",
            "app.main:app",
            "--reload",
            "--host", self.backend_host,
            "--port", str(self.backend_port),
        ]

        # 在 Windows 上需要使用 shell=True 来正确处理路径
        kwargs = {
            "cwd": self.backend_dir,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "bufsize": 1,
        }

        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            # Windows 使用 shell=True 并将命令转为字符串
            kwargs["shell"] = True
            cmd = " ".join(cmd)

        self.backend_process = subprocess.Popen(cmd, **kwargs)

        # 启动日志读取线程
        threading.Thread(
            target=self._read_process_output,
            args=(self.backend_process, "BACKEND"),
            daemon=True,
        ).start()

    def start_frontend(self):
        """启动前端服务"""
        self.log(f"正在启动前端服务...")
        self.log(f"前端地址: http://{self.frontend_host}:{self.frontend_port}")

        # 设置环境变量指定端口
        env = os.environ.copy()
        env["VITE_PORT"] = str(self.frontend_port)
        env["VITE_HOST"] = self.frontend_host

        cmd = ["npm", "run", "dev", "--", "--port", str(self.frontend_port), "--host", self.frontend_host]

        kwargs = {
            "cwd": self.frontend_dir,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "bufsize": 1,
            "env": env,
        }

        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
            # Windows 使用 shell=True 并将命令转为字符串
            kwargs["shell"] = True
            cmd = " ".join(cmd)

        self.frontend_process = subprocess.Popen(cmd, **kwargs)

        # 启动日志读取线程
        threading.Thread(
            target=self._read_process_output,
            args=(self.frontend_process, "FRONTEND"),
            daemon=True,
        ).start()

    def _read_process_output(self, process: subprocess.Popen, source: str):
        """读取进程输出并打印"""
        try:
            # 使用二进制模式读取，然后解码，处理编码错误
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                # 尝试多种编码解码
                for encoding in ['utf-8', 'gbk', 'gb2312', 'cp936', 'latin-1']:
                    try:
                        decoded_line = line.decode(encoding).rstrip()
                        if decoded_line:
                            self.log(decoded_line, source)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    # 所有编码都失败，使用忽略错误的方式
                    decoded_line = line.decode('utf-8', errors='ignore').rstrip()
                    if decoded_line:
                        self.log(decoded_line, source)
        except Exception as e:
            if not self.shutdown_event.is_set():
                self.log(f"读取输出出错: {e}", "ERROR")

    def stop_all(self):
        """停止所有服务"""
        self.log("正在停止所有服务...")
        self.shutdown_event.set()

        # 停止后端
        if self.backend_process and self.backend_process.poll() is None:
            self.log("正在停止后端服务...", "BACKEND")
            self._terminate_process(self.backend_process)

        # 停止前端
        if self.frontend_process and self.frontend_process.poll() is None:
            self.log("正在停止前端服务...", "FRONTEND")
            self._terminate_process(self.frontend_process)

        self.log("所有服务已停止")

    def _terminate_process(self, process: subprocess.Popen):
        """终止进程"""
        try:
            if sys.platform == "win32":
                # Windows: 使用 taskkill 终止进程树
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    capture_output=True,
                    check=False,
                )
            else:
                # Unix: 先发送 SIGTERM，等待后发送 SIGKILL
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        except Exception as e:
            self.log(f"终止进程时出错: {e}", "ERROR")

    def run(self):
        """运行服务管理器"""
        self.log("=" * 50)
        self.log("DevFlow Engine 启动器")
        self.log("=" * 50)

        # 检查依赖
        if not self.check_dependencies():
            sys.exit(1)

        # 设置信号处理
        def signal_handler(signum, frame):
            self.log("\n接收到中断信号，正在关闭...")
            self.stop_all()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)

        # 启动服务
        try:
            if self.enable_backend:
                self.start_backend()
                time.sleep(1)  # 给后端一点启动时间

            if self.enable_frontend:
                self.start_frontend()

            self.log("-" * 50)
            self.log("所有服务已启动")
            if self.enable_backend:
                self.log(f"  后端: http://{self.backend_host}:{self.backend_port}")
            if self.enable_frontend:
                self.log(f"  前端: http://{self.frontend_host}:{self.frontend_port}")
            self.log("-" * 50)
            self.log("按 Ctrl+C 停止所有服务")

            # 等待进程结束
            while True:
                backend_running = (
                    self.backend_process is not None
                    and self.backend_process.poll() is None
                )
                frontend_running = (
                    self.frontend_process is not None
                    and self.frontend_process.poll() is None
                )

                # 如果任一服务意外退出，检查是否需要停止
                if self.enable_backend and not backend_running:
                    self.log("后端服务意外退出", "ERROR")
                    break

                if self.enable_frontend and not frontend_running:
                    self.log("前端服务意外退出", "ERROR")
                    break

                if not backend_running and not frontend_running:
                    break

                time.sleep(0.5)

        except KeyboardInterrupt:
            pass
        finally:
            self.stop_all()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="DevFlow Engine 统一启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python server.py                          # 启动前后端（默认配置）
  python server.py --backend-port 8080      # 指定后端端口
  python server.py --frontend-port 3000     # 指定前端端口
  python server.py --no-frontend            # 只启动后端
  python server.py --no-backend             # 只启动前端
        """,
    )

    parser.add_argument(
        "--backend-port",
        type=int,
        default=19999,
        help="后端服务端口 (默认: 19999)",
    )
    parser.add_argument(
        "--frontend-port",
        type=int,
        default=3000,
        help="前端服务端口 (默认: 3000)",
    )
    parser.add_argument(
        "--backend-host",
        type=str,
        default="127.0.0.1",
        help="后端服务主机 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--frontend-host",
        type=str,
        default="127.0.0.1",
        help="前端服务主机 (默认: 127.0.0.1)",
    )
    parser.add_argument(
        "--no-backend",
        action="store_true",
        help="不启动后端服务",
    )
    parser.add_argument(
        "--no-frontend",
        action="store_true",
        help="不启动前端服务",
    )

    args = parser.parse_args()

    # 验证至少启动一个服务
    if args.no_backend and args.no_frontend:
        parser.error("不能同时禁用前后端服务")

    manager = ServerManager(
        backend_port=args.backend_port,
        frontend_port=args.frontend_port,
        backend_host=args.backend_host,
        frontend_host=args.frontend_host,
        enable_backend=not args.no_backend,
        enable_frontend=not args.no_frontend,
    )

    manager.run()


if __name__ == "__main__":
    main()
