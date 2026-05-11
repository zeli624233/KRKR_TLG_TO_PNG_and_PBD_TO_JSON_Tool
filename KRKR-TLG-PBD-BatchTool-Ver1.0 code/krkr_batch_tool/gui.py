from __future__ import annotations

import multiprocessing as mp
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .common import default_workers, full_workers, worker_choices
from .pbd_convert import (
    PbdConfigError,
    clean_temp,
    configure_plugin_folder,
    convert_pbd_batch,
    doctor_message,
    ensure_pbd_config_folder,
    missing_pbd_config_files,
)
from .tlg_convert import convert_tlg_batch


def _split_inputs(value: str) -> list[str]:
    return [x.strip().strip('"') for x in value.replace("\n", ";").split(";") if x.strip()]


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KRKR TLG/PBD 批处理工具 Ver1.0")
        self.geometry("920x680")
        self.minsize(860, 620)
        self.running = False
        self._build_ui()
        ensure_pbd_config_folder()
        self.log("软件已启动。TLG 转 PNG 使用内置解码器；PBD/JSON 使用内置 PBDConverter。")

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)
        nb = ttk.Notebook(root)
        nb.pack(fill="both", expand=True)

        self.tlg_tab = ttk.Frame(nb, padding=8)
        self.pbd_tab = ttk.Frame(nb, padding=8)
        self.tools_tab = ttk.Frame(nb, padding=8)
        nb.add(self.tlg_tab, text="TLG 转 PNG")
        nb.add(self.pbd_tab, text="PBD / JSON 转换")
        nb.add(self.tools_tab, text="配置 / 工具")

        self._build_tlg_tab()
        self._build_pbd_tab()
        self._build_tools_tab()

        bottom = ttk.LabelFrame(root, text="进度与日志", padding=8)
        bottom.pack(fill="both", expand=True, pady=(8, 0))
        self.progress = ttk.Progressbar(bottom, maximum=100)
        self.progress.pack(fill="x")
        self.progress_label = ttk.Label(bottom, text="等待任务")
        self.progress_label.pack(anchor="w", pady=(3, 5))
        self.log_text = tk.Text(bottom, height=12, wrap="none")
        self.log_text.pack(fill="both", expand=True, side="left")
        ybar = ttk.Scrollbar(bottom, orient="vertical", command=self.log_text.yview)
        ybar.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=ybar.set)

    def _path_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, filetypes: list[tuple[str, str]] | None = None) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=3, padx=4)
        ttk.Button(parent, text="选文件", command=lambda: self._choose_file(var, filetypes)).grid(row=row, column=2, padx=2)
        ttk.Button(parent, text="选目录", command=lambda: self._choose_dir(var)).grid(row=row, column=3, padx=2)
        parent.columnconfigure(1, weight=1)

    def _build_tlg_tab(self) -> None:
        frm = self.tlg_tab
        self.tlg_input = tk.StringVar()
        self.tlg_output = tk.StringVar()
        self.tlg_workers = tk.IntVar(value=default_workers())
        self.tlg_recursive = tk.BooleanVar(value=True)
        self.tlg_mirror = tk.BooleanVar(value=True)
        self.tlg_overwrite = tk.BooleanVar(value=False)
        self.tlg_optimize = tk.BooleanVar(value=False)
        self.tlg_suffix = tk.StringVar(value="")

        self._path_row(frm, 0, "输入 TLG 文件/目录", self.tlg_input, [("TLG 文件", "*.tlg"), ("所有文件", "*.*")])
        ttk.Label(frm, text="多个输入可用英文分号 ; 分隔").grid(row=1, column=1, sticky="w")
        self._path_row(frm, 2, "输出文件/目录", self.tlg_output, [("PNG 文件", "*.png"), ("所有文件", "*.*")])

        opt = ttk.LabelFrame(frm, text="批处理选项", padding=8)
        opt.grid(row=3, column=0, columnspan=4, sticky="ew", pady=8)
        ttk.Checkbutton(opt, text="递归扫描子目录", variable=self.tlg_recursive).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opt, text="输出目录保留原目录结构", variable=self.tlg_mirror).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(opt, text="覆盖已存在 PNG", variable=self.tlg_overwrite).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(opt, text="PNG optimize（更小但更慢）", variable=self.tlg_optimize).grid(row=0, column=3, sticky="w")
        ttk.Label(opt, text="线程/进程数").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(opt, textvariable=self.tlg_workers, values=worker_choices(), width=8, state="readonly").grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(opt, text="输出文件名后缀").grid(row=1, column=2, sticky="e", pady=(8, 0))
        ttk.Entry(opt, textvariable=self.tlg_suffix, width=16).grid(row=1, column=3, sticky="w", pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=4, sticky="w", pady=8)
        ttk.Button(btns, text="开始 TLG→PNG", command=self.start_tlg).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="使用全部 CPU", command=lambda: self.tlg_workers.set(full_workers())).pack(side="left")

    def _build_pbd_tab(self) -> None:
        frm = self.pbd_tab
        self.pbd_mode = tk.StringVar(value="pbd2json")
        self.pbd_input = tk.StringVar()
        self.pbd_output = tk.StringVar()
        self.plugin_dir = tk.StringVar()
        self.pbd_workers = tk.IntVar(value=default_workers())
        self.pbd_recursive = tk.BooleanVar(value=True)
        self.pbd_mirror = tk.BooleanVar(value=True)
        self.pbd_overwrite = tk.BooleanVar(value=False)
        self.pbd_keep_temp = tk.BooleanVar(value=False)
        self.pbd_suffix = tk.StringVar(value="")
        self.pbd_timeout = tk.IntVar(value=300)

        modebox = ttk.LabelFrame(frm, text="转换方向", padding=8)
        modebox.grid(row=0, column=0, columnspan=4, sticky="ew")
        ttk.Radiobutton(modebox, text="PBD → JSON", value="pbd2json", variable=self.pbd_mode).pack(side="left", padx=(0, 15))
        ttk.Radiobutton(modebox, text="JSON → PBD", value="json2pbd", variable=self.pbd_mode).pack(side="left")

        self._path_row(frm, 1, "输入文件/目录", self.pbd_input, [("PBD/JSON", "*.pbd *.json"), ("所有文件", "*.*")])
        ttk.Label(frm, text="多个输入可用英文分号 ; 分隔").grid(row=2, column=1, sticky="w")
        self._path_row(frm, 3, "输出文件/目录", self.pbd_output, [("PBD/JSON", "*.pbd *.json"), ("所有文件", "*.*")])

        ttk.Label(frm, text="游戏 plugin 文件夹").grid(row=4, column=0, sticky="w", pady=3)
        ttk.Entry(frm, textvariable=self.plugin_dir).grid(row=4, column=1, sticky="ew", pady=3, padx=4)
        ttk.Button(frm, text="选择 plugin", command=lambda: self._choose_dir(self.plugin_dir)).grid(row=4, column=2, padx=2)
        ttk.Button(frm, text="复制 DLL 到配置", command=self.configure_plugin).grid(row=4, column=3, padx=2)

        opt = ttk.LabelFrame(frm, text="批处理选项", padding=8)
        opt.grid(row=5, column=0, columnspan=4, sticky="ew", pady=8)
        ttk.Checkbutton(opt, text="递归扫描子目录", variable=self.pbd_recursive).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opt, text="输出目录保留原目录结构", variable=self.pbd_mirror).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(opt, text="覆盖已存在文件", variable=self.pbd_overwrite).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(opt, text="保留临时目录", variable=self.pbd_keep_temp).grid(row=0, column=3, sticky="w")
        ttk.Label(opt, text="并行进程数").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(opt, textvariable=self.pbd_workers, values=worker_choices(), width=8, state="readonly").grid(row=1, column=1, sticky="w", pady=(8, 0))
        ttk.Label(opt, text="输出文件名后缀").grid(row=1, column=2, sticky="e", pady=(8, 0))
        ttk.Entry(opt, textvariable=self.pbd_suffix, width=16).grid(row=1, column=3, sticky="w", pady=(8, 0))
        ttk.Label(opt, text="单文件超时秒数").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(opt, textvariable=self.pbd_timeout, width=10).grid(row=2, column=1, sticky="w", pady=(8, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=4, sticky="w", pady=8)
        ttk.Button(btns, text="开始 PBD/JSON 转换", command=self.start_pbd).pack(side="left", padx=(0, 6))
        ttk.Button(btns, text="使用全部 CPU", command=lambda: self.pbd_workers.set(full_workers())).pack(side="left")

    def _build_tools_tab(self) -> None:
        frm = self.tools_tab
        ttk.Button(frm, text="PBD 配置自检", command=self.show_doctor).grid(row=0, column=0, sticky="w", padx=4, pady=4)
        ttk.Button(frm, text="打开/创建 PBD 配置目录", command=self.open_pbd_config).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(frm, text="清理临时转换目录", command=self.clean_temp_ui).grid(row=0, column=2, sticky="w", padx=4, pady=4)
        info = (
            "命令行示例：\n"
            "python -m krkr_batch_tool tlg2png D:\\input -o D:\\out -r -j 8 --overwrite\n"
            "python -m krkr_batch_tool pbd2json D:\\pbd -o D:\\json -r --plugin-dir D:\\game\\plugin\n"
            "python -m krkr_batch_tool json2pbd D:\\json -o D:\\pbd -r -j 4\n"
            "python -m krkr_batch_tool doctor\n"
        )
        txt = tk.Text(frm, height=14, wrap="word")
        txt.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=8)
        txt.insert("1.0", info)
        txt.configure(state="disabled")
        frm.columnconfigure(3, weight=1)
        frm.rowconfigure(1, weight=1)

    def _choose_file(self, var: tk.StringVar, filetypes: list[tuple[str, str]] | None = None) -> None:
        path = filedialog.askopenfilename(filetypes=filetypes or [("所有文件", "*.*")])
        if path:
            var.set(path)

    def _choose_dir(self, var: tk.StringVar) -> None:
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def thread_log(self, message: str) -> None:
        self.after(0, lambda: self.log(message))

    def thread_progress(self, done: int, total: int, message: str) -> None:
        def update() -> None:
            pct = int(done / total * 100) if total else 0
            self.progress.configure(value=pct)
            self.progress_label.configure(text=f"{done}/{total}  {message}")
        self.after(0, update)

    def _set_running(self, running: bool) -> None:
        self.running = running
        self.progress.configure(value=0 if running else self.progress.cget("value"))

    def _run_background(self, title: str, func) -> None:
        if self.running:
            messagebox.showwarning("任务运行中", "请等待当前任务结束。")
            return
        self._set_running(True)
        self.log(f"===== {title} 开始 =====")

        def worker() -> None:
            try:
                results = func()
                ok = sum(1 for r in results if r.ok and not r.skipped)
                skipped = sum(1 for r in results if r.skipped)
                failed = sum(1 for r in results if not r.ok)
                self.thread_log(f"===== {title} 结束：完成 {ok}，跳过 {skipped}，失败 {failed} =====")
                self.after(0, lambda: messagebox.showinfo("任务完成", f"完成 {ok}，跳过 {skipped}，失败 {failed}"))
            except Exception as exc:
                self.thread_log(f"[错误] {exc}")
                self.after(0, lambda e=exc: messagebox.showerror("任务失败", str(e)))
            finally:
                self.after(0, lambda: self._set_running(False))

        threading.Thread(target=worker, daemon=True).start()

    def start_tlg(self) -> None:
        inputs = _split_inputs(self.tlg_input.get())
        if not inputs:
            messagebox.showwarning("缺少输入", "请选择 TLG 文件或目录。")
            return
        output = self.tlg_output.get().strip() or None

        def run():
            return convert_tlg_batch(
                inputs,
                output=output,
                recursive=self.tlg_recursive.get(),
                mirror=self.tlg_mirror.get(),
                workers=int(self.tlg_workers.get()),
                overwrite=self.tlg_overwrite.get(),
                suffix=self.tlg_suffix.get(),
                optimize=self.tlg_optimize.get(),
                progress=self.thread_progress,
                log=self.thread_log,
            )
        self._run_background("TLG→PNG", run)

    def _ensure_plugin_before_pbd(self) -> bool:
        plugin = self.plugin_dir.get().strip()
        if plugin:
            try:
                configure_plugin_folder(plugin)
                self.log("已复制 plugin DLL 到 PBD 配置目录。")
                return True
            except Exception as exc:
                messagebox.showerror("plugin 配置失败", str(exc))
                return False
        missing = missing_pbd_config_files()
        need_dll = any(x in missing for x in ("json.dll", "PackinOne.dll"))
        if need_dll:
            messagebox.showinfo("需要选择 plugin 文件夹", "检测到还没有配置 json.dll / PackinOne.dll。请在下一步选择游戏的 plugin 文件夹。")
            folder = filedialog.askdirectory(title="选择游戏 plugin 文件夹")
            if not folder:
                return False
            try:
                configure_plugin_folder(folder)
                self.plugin_dir.set(folder)
                self.log("已复制 plugin DLL 到 PBD 配置目录。")
                return True
            except Exception as exc:
                messagebox.showerror("plugin 配置失败", str(exc))
                return False
        return True

    def start_pbd(self) -> None:
        inputs = _split_inputs(self.pbd_input.get())
        if not inputs:
            messagebox.showwarning("缺少输入", "请选择 PBD/JSON 文件或目录。")
            return
        if not self._ensure_plugin_before_pbd():
            return
        output = self.pbd_output.get().strip() or None

        def run():
            return convert_pbd_batch(
                inputs,
                mode=self.pbd_mode.get(),
                output=output,
                recursive=self.pbd_recursive.get(),
                mirror=self.pbd_mirror.get(),
                workers=int(self.pbd_workers.get()),
                overwrite=self.pbd_overwrite.get(),
                suffix=self.pbd_suffix.get(),
                plugin_dir=None,
                keep_temp=self.pbd_keep_temp.get(),
                timeout=int(self.pbd_timeout.get()),
                progress=self.thread_progress,
                log=self.thread_log,
            )
        self._run_background("PBD/JSON 转换", run)

    def configure_plugin(self) -> None:
        folder = self.plugin_dir.get().strip()
        if not folder:
            folder = filedialog.askdirectory(title="选择游戏 plugin 文件夹")
            if not folder:
                return
            self.plugin_dir.set(folder)
        try:
            cfg = configure_plugin_folder(folder)
            messagebox.showinfo("配置完成", f"已复制 json.dll 和 PackinOne.dll 到：\n{cfg}")
            self.log(f"PBD plugin DLL 已配置：{cfg}")
        except Exception as exc:
            messagebox.showerror("配置失败", str(exc))

    def show_doctor(self) -> None:
        msg = doctor_message()
        self.log(msg)
        messagebox.showinfo("PBD 配置自检", msg)

    def open_pbd_config(self) -> None:
        path = ensure_pbd_config_folder()
        self.log(f"PBD 配置目录：{path}")
        try:
            import os
            os.startfile(path)  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo("PBD 配置目录", str(path))

    def clean_temp_ui(self) -> None:
        clean_temp()
        self.log("已清理临时转换目录。")
        messagebox.showinfo("完成", "已清理临时转换目录。")


def main() -> None:
    mp.freeze_support()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
