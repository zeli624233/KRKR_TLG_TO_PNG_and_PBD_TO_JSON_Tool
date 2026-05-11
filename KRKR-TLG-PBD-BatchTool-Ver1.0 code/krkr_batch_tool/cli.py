from __future__ import annotations

import argparse
import multiprocessing as mp
import sys
from pathlib import Path

from .common import default_workers, full_workers, iter_files
from .pbd_convert import (
    PbdConfigError,
    clean_temp,
    configure_plugin_folder,
    convert_pbd_batch,
    doctor_message,
    ensure_pbd_config_folder,
)
from .tlg_convert import convert_tlg_batch


def _print_progress(done: int, total: int, message: str) -> None:
    if total <= 0:
        print(message)
    else:
        print(f"[{done}/{total}] {message}")


def _print_log(message: str) -> None:
    print(message)


def add_common_batch_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("inputs", nargs="+", help="输入文件或目录，可传多个。")
    parser.add_argument("-o", "--output", help="输出文件或输出目录。不填时输出到源文件旁边。")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归扫描子目录。")
    parser.add_argument("-j", "--workers", type=int, default=default_workers(), help=f"并行线程/进程数，默认 CPU 50%%+1：{default_workers()}。")
    parser.add_argument("--full-workers", action="store_true", help=f"使用全部 CPU 逻辑线程：{full_workers()}。")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已存在的输出文件。")
    parser.add_argument("--suffix", default="", help="给输出文件名追加后缀，例如 _conv。")
    parser.add_argument("--no-mirror", action="store_true", help="输出到目录时不保留源目录结构。")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要执行的转换，不实际写文件。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="krkr-tool",
        description="TLG->PNG、PBD->JSON、JSON->PBD 批处理工具。",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="打开图形界面。")

    tlg = sub.add_parser("tlg2png", help="转换 TLG 到 PNG，支持批处理。")
    add_common_batch_options(tlg)
    tlg.add_argument("--optimize-png", action="store_true", help="保存 PNG 时启用 Pillow optimize，体积可能更小但更慢。")

    pbd2json = sub.add_parser("pbd2json", help="转换 PBD 到 JSON，支持批处理。")
    add_common_batch_options(pbd2json)
    pbd2json.add_argument("--plugin-dir", help="游戏 plugin 文件夹，包含 json.dll 和 PackinOne.dll；会自动复制到配置目录。")
    pbd2json.add_argument("--keep-temp", action="store_true", help="保留每个 PBD 转换任务的临时目录，方便排查问题。")
    pbd2json.add_argument("--timeout", type=int, default=300, help="单个文件转换超时秒数，默认 300。")

    json2pbd = sub.add_parser("json2pbd", help="转换 JSON 到 PBD，支持批处理。")
    add_common_batch_options(json2pbd)
    json2pbd.add_argument("--plugin-dir", help="游戏 plugin 文件夹，包含 json.dll 和 PackinOne.dll；会自动复制到配置目录。")
    json2pbd.add_argument("--keep-temp", action="store_true", help="保留每个 JSON 转换任务的临时目录，方便排查问题。")
    json2pbd.add_argument("--timeout", type=int, default=300, help="单个文件转换超时秒数，默认 300。")

    cfg = sub.add_parser("config-plugin", help="配置 PBD 所需的游戏 plugin 文件夹。")
    cfg.add_argument("plugin_dir", help="游戏 plugin 文件夹，必须包含 json.dll 和 PackinOne.dll。")

    scan = sub.add_parser("scan", help="扫描目录中的可转换文件。")
    scan.add_argument("inputs", nargs="+", help="输入文件或目录，可传多个。")
    scan.add_argument("--ext", action="append", choices=["tlg", "pbd", "json"], help="只扫描指定类型；可重复。默认扫描全部。")
    scan.add_argument("-r", "--recursive", action="store_true", help="递归扫描子目录。")

    sub.add_parser("doctor", help="检查 PBDConverter、data.xp3、json.dll、PackinOne.dll 配置。")
    sub.add_parser("clean-temp", help="清理 PBD 批处理临时转换目录。")
    return parser


def _workers(args: argparse.Namespace) -> int:
    return full_workers() if getattr(args, "full_workers", False) else max(1, int(args.workers))


def main(argv: list[str] | None = None) -> int:
    mp.freeze_support()
    parser = build_parser()
    args = parser.parse_args(argv)

    # Double-click python -m package or run without args: open GUI.
    if not args.command or args.command == "gui":
        from .gui import main as gui_main
        gui_main()
        return 0

    try:
        if args.command == "tlg2png":
            results = convert_tlg_batch(
                args.inputs,
                output=args.output,
                recursive=args.recursive,
                mirror=not args.no_mirror,
                workers=_workers(args),
                overwrite=args.overwrite,
                suffix=args.suffix,
                optimize=args.optimize_png,
                dry_run=args.dry_run,
                progress=_print_progress,
                log=_print_log,
            )
            return 0 if all(r.ok for r in results) else 2

        if args.command in {"pbd2json", "json2pbd"}:
            results = convert_pbd_batch(
                args.inputs,
                mode=args.command,
                output=args.output,
                recursive=args.recursive,
                mirror=not args.no_mirror,
                workers=_workers(args),
                overwrite=args.overwrite,
                suffix=args.suffix,
                plugin_dir=args.plugin_dir,
                keep_temp=args.keep_temp,
                timeout=args.timeout,
                dry_run=args.dry_run,
                progress=_print_progress,
                log=_print_log,
            )
            return 0 if all(r.ok for r in results) else 2

        if args.command == "config-plugin":
            cfg = configure_plugin_folder(args.plugin_dir)
            print(f"已配置 PBD plugin DLL：{cfg}")
            return 0

        if args.command == "scan":
            exts = args.ext or ["tlg", "pbd", "json"]
            files = iter_files(args.inputs, [f".{e}" for e in exts], recursive=args.recursive)
            print(f"找到 {len(files)} 个文件：")
            for f in files:
                print(f)
            return 0

        if args.command == "doctor":
            ensure_pbd_config_folder()
            print(doctor_message())
            return 0

        if args.command == "clean-temp":
            clean_temp()
            print("已清理临时转换目录。")
            return 0

    except PbdConfigError as exc:
        print(str(exc), file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("用户取消。", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
