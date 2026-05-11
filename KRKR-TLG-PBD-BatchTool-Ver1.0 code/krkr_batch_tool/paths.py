from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "KRKR_TLG_PBD_Tool"
PBD_CONFIG_DIR_NAME = "PBD文件解析配置"
PBD_ASSET_DIR_NAME = "pbd_converter_assets"
TEMP_DIR_NAME = "临时转换目录"


def program_base_dir() -> Path:
    """Return the writable folder beside the source tree or frozen EXE."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(*parts: str) -> Path:
    """Return a bundled-resource path for source runs and PyInstaller builds."""
    if getattr(sys, "_MEIPASS", None):
        return Path(sys._MEIPASS).joinpath(*parts)  # type: ignore[attr-defined]
    return program_base_dir().joinpath(*parts)


def pbd_config_dir() -> Path:
    return program_base_dir() / PBD_CONFIG_DIR_NAME


def temp_root_dir() -> Path:
    return program_base_dir() / TEMP_DIR_NAME
