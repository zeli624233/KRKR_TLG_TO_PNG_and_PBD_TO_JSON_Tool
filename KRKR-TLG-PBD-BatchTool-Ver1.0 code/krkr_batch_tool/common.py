from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

ProgressCallback = Callable[[int, int, str], None]
LogCallback = Callable[[str], None]


def default_workers() -> int:
    count = os.cpu_count() or 1
    return max(1, min(count, count // 2 + 1))


def full_workers() -> int:
    return max(1, os.cpu_count() or 1)


def worker_choices() -> list[int]:
    count = os.cpu_count() or 1
    values = sorted({1, 2, 3, 4, 6, 8, 12, 16, 24, 32, default_workers(), count})
    return [v for v in values if v <= count]


def normalize_ext(ext: str) -> str:
    ext = ext.strip().lower()
    return ext if ext.startswith(".") else f".{ext}"


def iter_files(inputs: Sequence[str | Path], extensions: Iterable[str], recursive: bool = False) -> list[Path]:
    exts = {normalize_ext(e) for e in extensions}
    result: list[Path] = []
    seen: set[str] = set()
    for raw in inputs:
        path = Path(raw).expanduser()
        if path.is_file():
            if path.suffix.lower() in exts:
                key = str(path.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    result.append(path.resolve())
        elif path.is_dir():
            globber = path.rglob if recursive else path.glob
            for item in globber("*"):
                if item.is_file() and item.suffix.lower() in exts:
                    key = str(item.resolve()).lower()
                    if key not in seen:
                        seen.add(key)
                        result.append(item.resolve())
    result.sort(key=lambda p: str(p).lower())
    return result


def output_path_for(input_file: Path, input_root: Path | None, output: Path | None, new_ext: str, mirror: bool, suffix: str = "") -> Path:
    new_ext = normalize_ext(new_ext)
    if output is None:
        return input_file.with_name(input_file.stem + suffix + new_ext)
    output = output.expanduser()
    if output.suffix and not output.exists() and not mirror and input_root is None:
        return output
    if input_root and mirror:
        try:
            rel = input_file.relative_to(input_root)
        except ValueError:
            rel = Path(input_file.name)
        return output / rel.with_name(rel.stem + suffix + new_ext)
    return output / (input_file.stem + suffix + new_ext)


def common_root_for_inputs(inputs: Sequence[str | Path]) -> Path | None:
    dirs: list[Path] = []
    for raw in inputs:
        p = Path(raw).expanduser()
        if p.is_dir():
            dirs.append(p.resolve())
        elif p.is_file():
            dirs.append(p.resolve().parent)
    if len(dirs) == 1:
        return dirs[0]
    return None


@dataclass(slots=True)
class ConvertResult:
    source: Path
    output: Path | None
    ok: bool
    skipped: bool = False
    message: str = ""
