"""暫時測試共用的初始化工具。"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from test_camera.parse_args import parse_args
from test_camera.test_camera import (
    TestCase,
    TestConfig,
    TestContext,
    TestRunner,
)
from tools_Common.adb import Adb


def bast() -> TestRunner:
    """建立暫時測試需要的測試環境並啟動 ADB log 捕獲。"""
    args = parse_args(tmp=True)
    config = TestConfig(rounds=1, interval=0)
    adb = Adb(serial=args.device)
    context = TestContext(adb, ROOT / ".tmp", config)
    runner = TestRunner(context)
    runner.start()
    return runner


def run_test(test: TestCase) -> None:
    """建立暫時測試環境並執行指定測試。"""
    runner = bast()
    runner.ctx.camera.launch_camera()

    try:
        runner.start_test(test=test)
        test.func(runner.ctx)
    finally:
        runner.stop()
