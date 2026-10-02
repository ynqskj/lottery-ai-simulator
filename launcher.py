import os
import sys
import traceback
import webbrowser
from pathlib import Path
from typing import Optional, Sequence
from urllib.error import URLError
from urllib.request import urlopen


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def configure_import_path(root: Optional[Path] = None) -> None:
    root_path = Path(root or application_root())
    src_path = root_path / "src"
    if src_path.exists():
        src_text = str(src_path)
        if src_text not in sys.path:
            sys.path.insert(0, src_text)


def ensure_runtime_dirs(root: Path) -> None:
    root_path = Path(root)
    for directory in (
        root_path / "data" / "normalized",
        root_path / "data" / "users",
        root_path / "reports" / "latest",
        root_path / "reports" / "users",
    ):
        directory.mkdir(parents=True, exist_ok=True)


def dashboard_url(host: str, port: int) -> str:
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}"


def dashboard_health_ok(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with urlopen(f"{dashboard_url(host, port)}/health", timeout=timeout) as response:
            return response.status == 200
    except (OSError, URLError):
        return False


def write_startup_error(root: Path, text: str) -> Path:
    path = Path(root) / "startup-error.log"
    path.write_text(text, encoding="utf-8")
    return path


def run_cli(argv: Optional[Sequence[str]] = None) -> int:
    configure_import_path()
    from lottery_sim.cli import main as cli_main

    return cli_main(list(argv or ()))


def run_dashboard(
    root: Optional[Path] = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    root_path = Path(root or application_root())
    configure_import_path(root_path)
    ensure_runtime_dirs(root_path)
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    if getattr(sys, "frozen", False):
        os.environ["LOTTERY_CLI_EXE"] = sys.executable
    url = dashboard_url(host, port)
    if dashboard_health_ok(host, port):
        print(f"检测到仪表盘已在运行：{url}")
        if open_browser:
            webbrowser.open(url)
        return

    try:
        from lottery_sim.fastapi_app import serve_fastapi_dashboard

        serve_fastapi_dashboard(
            reports_dir=root_path / "reports" / "latest",
            host=host,
            port=port,
            open_browser=open_browser,
            repo_root=root_path,
        )
    except RuntimeError as exc:
        print(f"{exc}; falling back to the local single-user server.")
        from lottery_sim.dashboard import serve_dashboard

        serve_dashboard(
            reports_dir=root_path / "reports" / "latest",
            host=host,
            port=port,
            open_browser=open_browser,
            repo_root=root_path,
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    # Frozen Python does not apply PYTHONIOENCODING during interpreter startup.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--cli":
        return run_cli(args[1:])
    try:
        host = os.environ.get("LOTTERY_HOST", "127.0.0.1")
        port = int(os.environ.get("LOTTERY_PORT", "8765"))
        open_browser = os.environ.get("LOTTERY_OPEN_BROWSER", "1").lower() not in {"0", "false", "no"}
        run_dashboard(host=host, port=port, open_browser=open_browser)
        return 0
    except KeyboardInterrupt:
        return 130
    except BaseException:
        error_text = traceback.format_exc()
        print(error_text)
        try:
            log_path = write_startup_error(application_root(), error_text)
            print(f"启动失败，错误日志已写入：{log_path}")
        except OSError:
            pass
        if getattr(sys, "frozen", False):
            input("启动失败，按 Enter 退出...")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
