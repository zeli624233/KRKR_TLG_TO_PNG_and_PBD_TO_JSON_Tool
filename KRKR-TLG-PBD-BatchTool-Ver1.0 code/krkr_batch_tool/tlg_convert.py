from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

from .common import ConvertResult, LogCallback, ProgressCallback, common_root_for_inputs, default_workers, iter_files, output_path_for
from .tlg_decoder import TlgDecodeError, read_tlg


def _convert_one_tlg(args: tuple[str, str, bool, bool]) -> ConvertResult:
    src_s, out_s, overwrite, optimize = args
    src = Path(src_s)
    out = Path(out_s)
    try:
        if out.exists() and not overwrite:
            return ConvertResult(src, out, ok=True, skipped=True, message="已存在，跳过")
        out.parent.mkdir(parents=True, exist_ok=True)
        image = read_tlg(src)
        image.save(out, "PNG", optimize=optimize)
        return ConvertResult(src, out, ok=True, message="完成")
    except Exception as exc:  # worker process must serialize simple exception text
        return ConvertResult(src, out, ok=False, message=str(exc))


def collect_tlg_jobs(
    inputs: Sequence[str | Path],
    output: str | Path | None = None,
    recursive: bool = False,
    mirror: bool = True,
    suffix: str = "",
) -> list[tuple[Path, Path]]:
    files = iter_files(inputs, [".tlg"], recursive=recursive)
    out_root = Path(output).expanduser() if output else None
    if out_root is not None and out_root.suffix and len(files) == 1:
        return [(files[0], out_root)]
    common_root = common_root_for_inputs(inputs)
    jobs: list[tuple[Path, Path]] = []
    for f in files:
        out = output_path_for(f, common_root, out_root, ".png", mirror=mirror and out_root is not None, suffix=suffix)
        jobs.append((f, out))
    return jobs


def convert_tlg_batch(
    inputs: Sequence[str | Path],
    output: str | Path | None = None,
    recursive: bool = False,
    mirror: bool = True,
    workers: int | None = None,
    overwrite: bool = False,
    suffix: str = "",
    optimize: bool = False,
    dry_run: bool = False,
    progress: ProgressCallback | None = None,
    log: LogCallback | None = None,
) -> list[ConvertResult]:
    """Convert .tlg files to .png.

    TLG decoding is CPU heavy, so the batch path uses multiple processes.
    """
    jobs = collect_tlg_jobs(inputs, output=output, recursive=recursive, mirror=mirror, suffix=suffix)
    total = len(jobs)
    if progress:
        progress(0, total, f"找到 {total} 个 TLG 文件")
    if log:
        log(f"TLG 批处理：{total} 个文件，线程/进程数={workers or default_workers()}")
    if dry_run:
        results = [ConvertResult(src, out, ok=True, skipped=True, message="dry-run") for src, out in jobs]
        for idx, r in enumerate(results, 1):
            if progress:
                progress(idx, total, f"预览：{r.source} -> {r.output}")
        return results
    if not jobs:
        return []

    max_workers = max(1, int(workers or default_workers()))
    results: list[ConvertResult] = []
    payloads = [(str(src), str(out), overwrite, optimize) for src, out in jobs]

    # Single process gives better tracebacks during debugging and avoids Windows spawn overhead for one file.
    if max_workers == 1 or len(payloads) == 1:
        for idx, payload in enumerate(payloads, 1):
            r = _convert_one_tlg(payload)
            results.append(r)
            if log:
                log(_format_result(r))
            if progress:
                progress(idx, total, r.message)
        return results

    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_convert_one_tlg, p) for p in payloads]
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


def _format_result(r: ConvertResult) -> str:
    if r.ok and r.skipped:
        return f"[跳过] {r.source} -> {r.output}：{r.message}"
    if r.ok:
        return f"[完成] {r.source} -> {r.output}"
    return f"[失败] {r.source}：{r.message}"
