#!/usr/bin/env python3

from __future__ import annotations

from bast import run_test

from test_camera.test_camera import TestCase


def tmp_test(context):
    """錄影測試流程"""
    ui = context.resources.ui
    logger = context.resources.logger

    logger.info("按下快門...")
    ui.click_then_appear("B_錄影鍵", "B_停止錄影")

    logger.info("開始錄影...")
    context.camera.wait_record_time(target_sec=2)  # 等待錄影至少 2 秒

    logger.info("停止錄影...")
    ui.click_then_appear("B_停止錄影", "B_錄影鍵", timeout_ms=10000)


test = TestCase(
    key="video",
    func=tmp_test,
    test_name="錄影",
    mode="main",
    param="video",
    check_saved=True,
    alias="v",
)


if __name__ == "__main__":
    run_test(test)
