from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from .common import ConvertResult, LogCallback, ProgressCallback, common_root_for_inputs, default_workers, iter_files, output_path_for
from .paths import PBD_ASSET_DIR_NAME, pbd_config_dir, resource_path, temp_root_dir

PBD_DLL_FILES = ("json.dll", "PackinOne.dll")
PBD_RUNTIME_FILES = ("PBDConverter.exe", "PBDConverter.cf", "data.xp3")
PBD_EXE_NAMES = ("PBDConverter.exe", "tvpwin32.exe")


class PbdConfigError(RuntimeError):
    pass


class PbdConversionError(RuntimeError):
    pass


def ensure_pbd_config_folder() -> Path:
    cfg = pbd_config_dir()
    cfg.mkdir(parents=True, exist_ok=True)
    for name in PBD_RUNTIME_FILES:
        src = resource_path(PBD_ASSET_DIR_NAME, name)
        dst = cfg / name
        if src.exists() and (not dst.exists() or dst.stat().st_size != src.stat().st_size):
            try:
                shutil.copy2(src, dst)
            except Exception:
                # Report below through missing files if it really failed.
                pass
    readme = cfg / "请先阅读.txt"
    text = (
        "PBD 文件解析配置目录。\n\n"
        "本软件已内置 PBDConverter.exe、PBDConverter.cf、data.xp3。\n"
        "第一次转换 PBD/JSON 时，请在软件里选择游戏的 plugin 文件夹；\n"
        "软件会自动复制 json.dll 和 PackinOne.dll 到这里。\n\n"
        "注意：json.dll 和 PackinOne.dll 属于游戏文件，本工具包不内置。\n"
    )
    try:
        if not readme.exists() or readme.read_text(encoding="utf-8", errors="ignore") != text:
            readme.write_text(text, encoding="utf-8")
    except Exception:
        pass
    return cfg


def find_converter_exe() -> Path | None:
    cfg = ensure_pbd_config_folder()
    candidates: list[Path] = []
    for base in [cfg, resource_path(PBD_ASSET_DIR_NAME)]:
        for name in PBD_EXE_NAMES:
            candidates.append(base / name)
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    return None


def missing_pbd_config_files() -> list[str]:
    cfg = ensure_pbd_config_folder()
    missing: list[str] = []
    for name in PBD_RUNTIME_FILES:
        if not (cfg / name).exists():
            missing.append(name)
    if find_converter_exe() is None:
        missing.append("PBDConverter.exe 或 tvpwin32.exe")
    for name in PBD_DLL_FILES:
        if not (cfg / name).exists():
            missing.append(name)
    return missing


def pbd_configured() -> bool:
    return not missing_pbd_config_files()


def configure_plugin_folder(plugin_dir: str | Path) -> Path:
    plugin = Path(plugin_dir).expanduser().resolve()
    if not plugin.is_dir():
        raise PbdConfigError(f"不是有效的 plugin 文件夹：{plugin}")
    missing = [name for name in PBD_DLL_FILES if not (plugin / name).exists()]
    if missing:
        raise PbdConfigError("选择的文件夹中缺少：" + "、".join(missing))
    cfg = ensure_pbd_config_folder()
    for name in PBD_DLL_FILES:
        shutil.copy2(plugin / name, cfg / name)
    return cfg


def pbd_configuration_message() -> str:
    missing = missing_pbd_config_files()
    return (
        "PBD/JSON 转换配置未完成。\n\n"
        "缺少：" + ("、".join(missing) if missing else "无") + "\n\n"
        "处理方法：请选择游戏目录里的 plugin 文件夹，让软件自动复制 json.dll 和 PackinOne.dll。\n"
        f"配置目录：{ensure_pbd_config_folder()}"
    )


def collect_pbd_jobs(
    inputs: Sequence[str | Path],
    mode: str,
    output: str | Path | None = None,
    recursive: bool = False,
    mirror: bool = True,
    suffix: str = "",
) -> list[tuple[Path, Path]]:
    if mode not in {"pbd2json", "json2pbd"}:
        raise ValueError("mode must be pbd2json or json2pbd")
    src_ext = ".pbd" if mode == "pbd2json" else ".json"
    dst_ext = ".json" if mode == "pbd2json" else ".pbd"
    files = iter_files(inputs, [src_ext], recursive=recursive)
    out_root = Path(output).expanduser() if output else None
    if out_root is not None and out_root.suffix and len(files) == 1:
        return [(files[0], out_root)]
    common_root = common_root_for_inputs(inputs)
    jobs: list[tuple[Path, Path]] = []
    for f in files:
        out = output_path_for(f, common_root, out_root, dst_ext, mirror=mirror and out_root is not None, suffix=suffix)
        jobs.append((f, out))
    return jobs


def _run_pbd_converter(temp_input: Path, target: str, timeout: int) -> str:
    exe = find_converter_exe()
    if exe is None:
        raise PbdConfigError("没有找到 PBDConverter.exe。")
    cfg = ensure_pbd_config_folder()
    command = [str(exe), f"-input={temp_input}"]
    # PBDConverter README says target defaults to json. Only pass target for json -> pbd.
    if target == "pbd":
        command.append("-target=pbd")
    proc = subprocess.run(
        command,
        cwd=str(cfg),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        shell=False,
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise PbdConversionError(output.strip() or f"PBDConverter 返回错误码 {proc.returncode}")
    return output.strip()


def _convert_one_pbd(args: tuple[str, str, str, bool, bool, int, bool]) -> ConvertResult:
    src_s, out_s, target, overwrite, keep_temp, timeout, dry_run = args
    src = Path(src_s)
    out = Path(out_s)
    try:
        if out.exists() and not overwrite:
            return ConvertResult(src, out, ok=True, skipped=True, message="已存在，跳过")
        if dry_run:
            return ConvertResult(src, out, ok=True, skipped=True, message="dry-run")
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp_parent = temp_root_dir()
        tmp_parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = Path(tempfile.mkdtemp(prefix="pbd_job_", dir=str(tmp_parent)))
        try:
            temp_input = tmp_dir / src.name
            shutil.copy2(src, temp_input)
            _run_pbd_converter(temp_input, target=target, timeout=timeout)
            produced = temp_input.with_suffix(".json" if target == "json" else ".pbd")
            if not produced.exists():
                raise PbdConversionError(f"转换器没有生成预期文件：{produced.name}")
            if out.exists() and overwrite:
                out.unlink()
            shutil.move(str(produced), str(out))
            return ConvertResult(src, out, ok=True, message="完成")
        finally:
            if not keep_temp:
                shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        return ConvertResult(src, out, ok=False, message=str(exc))


def convert_pbd_batch(
    inputs: Sequence[str | Path],
    mode: str,
    output: str | Path | None = None,
    recursive: bool = False,
    mirror: bool = True,
    workers: int | None = None,
    overwrite: bool = False,
    suffix: str = "",
    plugin_dir: str | Path | None = None,
    keep_temp: bool = False,
    timeout: int = 300,
    dry_run: bool = False,
    progress: ProgressCallback | None = None,
    log: LogCallback | None = None,
) -> list[ConvertResult]:
    if plugin_dir:
        configure_plugin_folder(plugin_dir)
    missing = missing_pbd_config_files()
    if missing:
        raise PbdConfigError(pbd_configuration_message())

    target = "json" if mode == "pbd2json" else "pbd"
    jobs = collect_pbd_jobs(inputs, mode=mode, output=output, recursive=recursive, mirror=mirror, suffix=suffix)
    total = len(jobs)
    if progress:
        progress(0, total, f"找到 {total} 个文件")
    if log:
        log(f"{mode} 批处理：{total} 个文件，线程数={workers or default_workers()}")
    if not jobs:
        return []

    max_workers = max(1, int(workers or default_workers()))
    payloads = [(str(src), str(out), target, overwrite, keep_temp, timeout, dry_run) for src, out in jobs]
    results: list[ConvertResult] = []
    if max_workers == 1 or len(payloads) == 1:
        for idx, payload in enumerate(payloads, 1):
            r = _convert_one_pbd(payload)
            results.append(r)
            if log:
                log(_format_result(r))
            if progress:
                progress(idx, total, r.message)
        return results

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_convert_one_pbd, p) for p in payloads]
        for idx, fut in enumerate(as_completed(futures), 1):
            try:
                r = fut.result()
            except Exception as exc:
                r = ConvertResult(Path("?"), None, ok=False, message=str(exc))
            results.append(r)
            if log:
                log(_format_result(r))
            if progress:
                progress(idx, total, r.message)
    return results


def doctor_message() -> str:
    cfg = ensure_pbd_config_folder()
    lines = [
        "KRKR TLG/PBD 工具自检",
        f"程序目录：{cfg.parent}",
        f"PBD 配置目录：{cfg}",
        f"PBDConverter：{find_converter_exe() or '未找到'}",
    ]
    for name in [*PBD_RUNTIME_FILES, *PBD_DLL_FILES]:
        path = cfg / name
        lines.append(f"{'OK ' if path.exists() else '缺少'} {name}: {path}")
    if os.name != "nt":
        lines.append("提示：PBDConverter.exe 是 Windows 程序；PBD 转换建议在 Windows 上运行。")
    return "\n".join(lines)


def clean_temp() -> None:
    root = temp_root_dir()
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


def _format_result(r: ConvertResult) -> str:
    if r.ok and r.skipped:
        return f"[跳过] {r.source} -> {r.output}：{r.message}"
    if r.ok:
        return f"[完成] {r.source} -> {r.output}"
    return f"[失败] {r.source}：{r.message}"
