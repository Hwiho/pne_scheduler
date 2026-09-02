"""
Double-click GUI for scaling .sch current values.
"""
import os
import traceback
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from sch_current_rescaler import (
    C_RATE_DIGITS,
    CURRENT_DIGITS,
    FRACTION_C_RATE_TOLERANCE,
    build_batch_output_path,
    collect_current_fields,
    format_c_rate_display,
    format_mA,
    parse_capacity_list,
    scale_current_fields,
)


class RescalerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SCH Current Rescaler")
        self.geometry("820x580")
        self.minsize(760, 540)

        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.output_stem = tk.StringVar()
        self.old_capacity = tk.StringVar(value="100")
        self.new_capacities = tk.StringVar(value="100")

        self._build_ui()

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(6, weight=1)

        ttk.Label(root, text="원본 .sch 파일").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(root, textvariable=self.input_path).grid(row=0, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(root, text="찾기", command=self.pick_input).grid(row=0, column=2, pady=5)

        ttk.Label(root, text="출력 폴더").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Entry(root, textvariable=self.output_dir).grid(row=1, column=1, sticky="ew", padx=8, pady=5)
        ttk.Button(root, text="폴더 선택", command=self.pick_output_dir).grid(row=1, column=2, pady=5)

        ttk.Label(root, text="출력 파일명 stem").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(root, textvariable=self.output_stem).grid(row=2, column=1, sticky="ew", padx=8, pady=5)

        ttk.Label(root, text="기존 셀 용량 (mAh)").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(root, textvariable=self.old_capacity, width=16).grid(row=3, column=1, sticky="w", padx=8, pady=5)

        ttk.Label(root, text="변환할 용량 목록 (mAh)").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(root, textvariable=self.new_capacities).grid(row=4, column=1, sticky="ew", padx=8, pady=5)
        ttk.Label(root, text="쉼표로 구분").grid(row=4, column=2, sticky="w", pady=5)

        button_row = ttk.Frame(root)
        button_row.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(12, 8))
        ttk.Button(button_row, text="일괄 변환 실행", command=self.convert).pack(side="left")
        ttk.Button(button_row, text="원본 전류 보기", command=self.show_input_currents).pack(side="left", padx=8)
        ttk.Button(button_row, text="로그 지우기", command=self.clear_log).pack(side="left", padx=8)

        log_frame = ttk.LabelFrame(root, text="변환 로그")
        log_frame.grid(row=6, column=0, columnspan=3, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, wrap="none", height=18)
        self.log.grid(row=0, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=yscroll.set)

        self.write_log("전류 변환 대상: CCCV 전류, CCCV CV cut-off, CC 충전 전류, CC 방전 전류")
        self.write_log("Header safety limit 전류값은 변경하지 않습니다.")
        self.write_log(
            "정규화 정책: 1/3C 자동 인식 tolerance %.12gC, 그 외 C-rate 소수점 %d자리, 전류 소수점 %d자리 mA"
            % (FRACTION_C_RATE_TOLERANCE, C_RATE_DIGITS, CURRENT_DIGITS)
        )

    def pick_input(self):
        path = filedialog.askopenfilename(
            title="원본 .sch 파일 선택",
            filetypes=[("SCH files", "*.sch"), ("All files", "*.*")],
        )
        if not path:
            return
        self.input_path.set(path)
        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(path))
        if not self.output_stem.get():
            base = os.path.splitext(os.path.basename(path))[0]
            self.output_stem.set(base + "_rescaled")
        self.show_input_currents()

    def pick_output_dir(self):
        initial = self.output_dir.get() or os.path.dirname(self.input_path.get()) or os.getcwd()
        path = filedialog.askdirectory(
            title="출력 폴더 선택",
            initialdir=initial,
        )
        if path:
            self.output_dir.set(path)

    def clear_log(self):
        self.log.delete("1.0", "end")

    def write_log(self, text=""):
        self.log.insert("end", str(text) + "\n")
        self.log.see("end")
        self.update_idletasks()

    def _old_capacity_value_or_none(self):
        text = self.old_capacity.get().strip()
        if not text:
            return None
        value = float(text)
        if value <= 0:
            raise ValueError("기존 셀 용량은 0보다 커야 합니다.")
        return value

    def show_input_currents(self):
        try:
            input_path = self.input_path.get().strip()
            if not input_path:
                raise ValueError("원본 .sch 파일을 먼저 선택하세요.")
            if not os.path.exists(input_path):
                raise ValueError("원본 파일을 찾을 수 없습니다: %s" % input_path)

            capacity = self._old_capacity_value_or_none()
            with open(input_path, "rb") as f:
                src = f.read()
            summary = collect_current_fields(src, capacity)

            self.write_log("")
            self.write_log("원본 전류 목록")
            self.write_log("파일: %s" % input_path)
            self.write_log("Header size: %d bytes" % summary["header_size"])
            self.write_log("Step count: %d" % summary["step_count"])
            self.write_log("Current fields: %d" % len(summary["fields"]))
            if capacity:
                self.write_log("기존 셀 용량 기준: %g mAh" % capacity)
            self.write_log("")
            self.write_log(" step  kind          field              mA      C-rate")
            self.write_log(" ----  ------------  ------------  ----------  ----------")
            for item in summary["fields"][:160]:
                c_rate_value = item.get("canonical_c_rate", item.get("c_rate"))
                self.write_log(
                    "%5s  %-12s  %-12s  %10s  %10s"
                    % (
                        item["step"],
                        item["kind"],
                        item["field"],
                        format_mA(item["value"]),
                        format_c_rate_display(c_rate_value, item.get("c_rate_label")),
                    )
                )
            if len(summary["fields"]) > 160:
                self.write_log("... %d more current fields" % (len(summary["fields"]) - 160))
        except Exception as exc:
            self.write_log("")
            self.write_log("원본 전류 표시 오류: %s" % exc)

    def validate_inputs(self):
        input_path = self.input_path.get().strip()
        output_dir = self.output_dir.get().strip()
        output_stem = self.output_stem.get().strip()
        if not input_path:
            raise ValueError("원본 .sch 파일을 선택하세요.")
        if not os.path.exists(input_path):
            raise ValueError("원본 파일을 찾을 수 없습니다: %s" % input_path)
        if not output_dir:
            raise ValueError("출력 폴더를 지정하세요.")
        if os.path.exists(output_dir) and not os.path.isdir(output_dir):
            raise ValueError("출력 경로가 폴더가 아닙니다: %s" % output_dir)
        if not output_stem:
            raise ValueError("출력 파일명 stem을 입력하세요.")
        if any(sep in output_stem for sep in ("/", "\\")):
            raise ValueError("출력 파일명 stem에는 폴더 경로를 넣을 수 없습니다.")

        old_cap = float(self.old_capacity.get().strip())
        new_caps = parse_capacity_list(self.new_capacities.get())
        if old_cap <= 0:
            raise ValueError("셀 용량은 0보다 커야 합니다.")
        output_paths = [
            build_batch_output_path(output_dir, output_stem, new_cap)
            for new_cap in new_caps
        ]
        if len(set(output_paths)) != len(output_paths):
            raise ValueError("중복된 출력 파일명이 생깁니다. 용량 입력값을 확인하세요.")
        return input_path, output_dir, output_stem, old_cap, new_caps, output_paths

    def convert(self):
        try:
            input_path, output_dir, output_stem, old_cap, new_caps, output_paths = self.validate_inputs()
            self.write_log("")
            self.write_log("변환 시작")
            self.write_log("원본: %s" % input_path)
            self.write_log("출력 폴더: %s" % output_dir)
            self.write_log("출력 파일명 stem: %s" % output_stem)
            self.write_log("기존 용량: %g mAh" % old_cap)
            self.write_log("변환할 용량: %s" % ", ".join("%g" % cap for cap in new_caps))

            with open(input_path, "rb") as f:
                src = f.read()

            os.makedirs(output_dir, exist_ok=True)
            written_paths = []
            for new_cap, output_path in zip(new_caps, output_paths):
                out, summary = scale_current_fields(src, old_cap, new_cap)
                with open(output_path, "wb") as f:
                    f.write(out)
                written_paths.append(output_path)

                self.write_log("")
                self.write_log("출력: %s" % output_path)
                self.write_log("용량: %g mAh -> %g mAh" % (old_cap, new_cap))
                self.write_log("Header size: %d bytes" % summary["header_size"])
                self.write_log("Step count: %d" % summary["step_count"])
                self.write_log("Scale factor: %.12g" % summary["factor"])
                self.write_log(
                    "Canonicalization: 1/3C tolerance %.12gC, C-rate %d decimals, current %d decimals"
                    % (
                        summary.get("fraction_tolerance", 0),
                        summary["c_rate_digits"],
                        summary["current_digits"],
                    )
                )
                self.write_log("Changed fields: %d" % len(summary["changes"]))
                self.write_log("")
                self.write_log(" step  kind          field          old mA      new mA      C-rate")
                self.write_log(" ----  ------------  ------------  ----------  ----------  ----------")
                for ch in summary["changes"][:120]:
                    self.write_log(
                        "%5s  %-12s  %-12s  %10s  %10s  %s -> %s"
                        % (
                            ch["step"],
                            ch["kind"],
                            ch["field"],
                            format_mA(ch["old"], summary["current_digits"]),
                            format_mA(ch["new"], summary["current_digits"]),
                            format_c_rate_display(
                                ch["old_c"],
                                ch.get("old_c_label"),
                                summary["c_rate_digits"],
                            ),
                            format_c_rate_display(
                                ch["new_c"],
                                ch.get("new_c_label"),
                                summary["c_rate_digits"],
                            ),
                        )
                    )
                if len(summary["changes"]) > 120:
                    self.write_log("... %d more changed fields" % (len(summary["changes"]) - 120))
            self.write_log("")
            self.write_log("완료: %d개 파일 생성" % len(written_paths))
            messagebox.showinfo(
                "완료",
                "변환이 완료되었습니다.\n\n%d개 파일을 생성했습니다." % len(written_paths),
            )
        except Exception as exc:
            self.write_log("")
            self.write_log("오류: %s" % exc)
            self.write_log(traceback.format_exc())
            messagebox.showerror("오류", str(exc))


def main():
    app = RescalerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
