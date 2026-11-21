"""环境加载器测试：小但重要，因为它决定 key / 代理能不能被读到。

⚠️ 不用 pytest 的 tmp_path：它会写到系统临时目录，在某些受限环境（沙箱、CI 容器、
   Windows 的 Temp 权限异常）下会直接 PermissionError。改成在工作区内建临时目录，
   这样测试在任何环境都能跑——这也算一次可移植性修复。
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from rag.env import load_env, mask, proxy_url

TMP_DIR = Path(__file__).resolve().parent / "_tmp"


@pytest.fixture()
def tmp_dir():
    TMP_DIR.mkdir(exist_ok=True)
    yield TMP_DIR
    shutil.rmtree(TMP_DIR, ignore_errors=True)


def test_load_env_sets_missing_vars(tmp_dir, monkeypatch):
    env_file = tmp_dir / ".env"
    env_file.write_text("RAG_TEST_A=alpha\nRAG_TEST_B=\"beta\"\n# 注释行\n", encoding="utf-8")
    monkeypatch.delenv("RAG_TEST_A", raising=False)
    monkeypatch.delenv("RAG_TEST_B", raising=False)

    loaded = load_env(env_file)
    assert loaded["RAG_TEST_A"] == "alpha"
    assert os.environ["RAG_TEST_B"] == "beta"  # 引号被去掉


def test_existing_env_wins(tmp_dir, monkeypatch):
    """已存在的进程变量不能被 .env 覆盖（否则 CI 注入的值会被仓库文件顶掉）。"""
    env_file = tmp_dir / ".env"
    env_file.write_text("RAG_TEST_C=from_file\n", encoding="utf-8")
    monkeypatch.setenv("RAG_TEST_C", "from_process")
    load_env(env_file)
    assert os.environ["RAG_TEST_C"] == "from_process"


def test_missing_file_is_noop(tmp_dir):
    assert load_env(tmp_dir / "nope.env") == {}


def test_mask_never_leaks_full_key():
    assert mask(None) == "(未设置)"
    assert mask("short") == "(已设置，长度 5)"
    masked = mask("sk-1234567890abcdef")
    assert "1234567890" not in masked
    assert masked.startswith("sk-12")


def test_proxy_url_reads_env(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:7877")
    assert proxy_url() == "http://127.0.0.1:7877"
