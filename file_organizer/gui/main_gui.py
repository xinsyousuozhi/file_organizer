#!/usr/bin/env python3
"""
파일 정리 도구 GUI

tkinter 기반 그래픽 인터페이스
"""

import sys
import threading
import queue
from pathlib import Path
from typing import Optional, Set
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# 상위 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import OrganizerConfig
from src.organizer import FileOrganizer
from cli.cleanup_empty import cleanup_empty_folders, find_empty_folders


class FileOrganizerGUI:
    """파일 정리 도구 GUI 클래스"""

    # 기본 제외 폴더
    DEFAULT_EXCLUDED = {
        '.git', '.svn', '__pycache__', 'node_modules',
        '.venv', 'venv', '.idea', '.vscode',
        '_OrganizedFiles', '$RECYCLE.BIN', 'System Volume Information',
        '.cache', '.npm', '.yarn', 'dist', 'build', 'target',
        'file_organizer',
    }

    # 분류 대상 확장자
    DEFAULT_CLASSIFY_EXT = {
        # 문서
        '.pdf', '.doc', '.docx', '.hwp', '.hwpx',
        '.xls', '.xlsx', '.xlsm', '.csv',
        '.ppt', '.pptx', '.odt', '.ods', '.odp', '.rtf',
        # 이미지
        '.jpg', '.jpeg', '.png', '.gif', '.bmp',
        '.svg', '.webp', '.tiff', '.tif',
        # 압축
        '.zip', '.rar', '.7z', '.tar', '.gz',
    }

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("파일 정리 도구")
        self.root.geometry("800x700")
        self.root.minsize(600, 500)

        # 상태 변수
        self.target_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.archive_dir = tk.StringVar(value=str(Path.home() / "_OrganizedFiles"))
        self.dry_run = tk.BooleanVar(value=True)
        self.include_duplicates = tk.BooleanVar(value=True)
        self.include_classify = tk.BooleanVar(value=True)
        self.include_year = tk.BooleanVar(value=True)
        self.include_month = tk.BooleanVar(value=False)
        self.cleanup_empty = tk.BooleanVar(value=True)

        # 작업 상태
        self.is_running = False
        self.message_queue = queue.Queue()

        self._create_widgets()
        self._start_message_handler()

    def _create_widgets(self):
        """위젯 생성"""
        # 메인 프레임
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        # === 폴더 설정 ===
        folder_frame = ttk.LabelFrame(main_frame, text="폴더 설정", padding="5")
        folder_frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        folder_frame.columnconfigure(1, weight=1)

        # 대상 폴더
        ttk.Label(folder_frame, text="대상 폴더:").grid(row=0, column=0, sticky="w", padx=5)
        ttk.Entry(folder_frame, textvariable=self.target_dir).grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(folder_frame, text="찾아보기", command=self._browse_target).grid(row=0, column=2, padx=5)

        # 저장 폴더
        ttk.Label(folder_frame, text="저장 폴더:").grid(row=1, column=0, sticky="w", padx=5, pady=(5, 0))
        ttk.Entry(folder_frame, textvariable=self.archive_dir).grid(row=1, column=1, sticky="ew", padx=5, pady=(5, 0))
        ttk.Button(folder_frame, text="찾아보기", command=self._browse_archive).grid(row=1, column=2, padx=5, pady=(5, 0))

        # === 정리 옵션 ===
        option_frame = ttk.LabelFrame(main_frame, text="정리 옵션", padding="5")
        option_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        # 체크박스들
        ttk.Checkbutton(option_frame, text="중복 파일 처리 (SHA256 해싱)",
                        variable=self.include_duplicates).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Checkbutton(option_frame, text="문서/이미지 주제별 분류",
                        variable=self.include_classify).grid(row=0, column=1, sticky="w", padx=5)

        ttk.Checkbutton(option_frame, text="연도별 폴더 생성",
                        variable=self.include_year).grid(row=1, column=0, sticky="w", padx=5)
        ttk.Checkbutton(option_frame, text="월별 폴더 생성",
                        variable=self.include_month).grid(row=1, column=1, sticky="w", padx=5)

        ttk.Checkbutton(option_frame, text="완료 후 빈 폴더 정리",
                        variable=self.cleanup_empty).grid(row=2, column=0, sticky="w", padx=5)

        # === 실행 모드 ===
        mode_frame = ttk.LabelFrame(main_frame, text="실행 모드", padding="5")
        mode_frame.grid(row=2, column=0, sticky="ew", pady=(0, 10))

        ttk.Radiobutton(mode_frame, text="미리보기 (드라이 런)",
                        variable=self.dry_run, value=True).grid(row=0, column=0, padx=10)
        ttk.Radiobutton(mode_frame, text="실제 실행",
                        variable=self.dry_run, value=False).grid(row=0, column=1, padx=10)

        # === 버튼 ===
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, sticky="ew", pady=(0, 10))

        self.run_button = ttk.Button(button_frame, text="실행", command=self._run_organizer)
        self.run_button.pack(side="left", padx=5)

        self.stop_button = ttk.Button(button_frame, text="중지", command=self._stop_organizer, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        ttk.Button(button_frame, text="로그 지우기", command=self._clear_log).pack(side="left", padx=5)

        ttk.Button(button_frame, text="복원 도구", command=self._open_restore).pack(side="right", padx=5)

        # === 로그 출력 ===
        log_frame = ttk.LabelFrame(main_frame, text="실행 로그", padding="5")
        log_frame.grid(row=4, column=0, sticky="nsew", pady=(0, 10))
        main_frame.rowconfigure(4, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, wrap=tk.WORD)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")

        # === 상태 바 ===
        self.status_var = tk.StringVar(value="준비")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief="sunken")
        status_bar.grid(row=5, column=0, sticky="ew")

    def _browse_target(self):
        """대상 폴더 선택"""
        path = filedialog.askdirectory(title="대상 폴더 선택")
        if path:
            self.target_dir.set(path)

    def _browse_archive(self):
        """저장 폴더 선택"""
        path = filedialog.askdirectory(title="저장 폴더 선택")
        if path:
            self.archive_dir.set(path)

    def _log(self, message: str):
        """로그 메시지 큐에 추가"""
        self.message_queue.put(message)

    def _start_message_handler(self):
        """메시지 핸들러 시작"""
        def process_messages():
            try:
                while True:
                    msg = self.message_queue.get_nowait()
                    self.log_text.config(state="normal")
                    self.log_text.insert("end", msg + "\n")
                    self.log_text.see("end")
                    self.log_text.config(state="disabled")
            except queue.Empty:
                pass
            self.root.after(100, process_messages)

        self.root.after(100, process_messages)

    def _clear_log(self):
        """로그 지우기"""
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _run_organizer(self):
        """정리 실행"""
        if self.is_running:
            return

        # 경로 검증
        target = Path(self.target_dir.get())
        if not target.exists():
            messagebox.showerror("오류", f"대상 폴더가 존재하지 않습니다:\n{target}")
            return

        # 실제 실행 확인
        if not self.dry_run.get():
            confirm = messagebox.askyesno(
                "확인",
                "실제로 파일을 이동합니다.\n계속하시겠습니까?"
            )
            if not confirm:
                return

        self.is_running = True
        self.run_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_var.set("실행 중...")

        # 백그라운드 스레드에서 실행
        thread = threading.Thread(target=self._run_in_background, daemon=True)
        thread.start()

    def _run_in_background(self):
        """백그라운드 실행"""
        try:
            target = Path(self.target_dir.get())
            archive = Path(self.archive_dir.get())
            dry_run = self.dry_run.get()

            self._log("=" * 50)
            self._log(f"파일 정리 시작 {'(미리보기)' if dry_run else '(실제 실행)'}")
            self._log("=" * 50)
            self._log(f"대상 폴더: {target}")
            self._log(f"저장 폴더: {archive}")

            # 설정 생성
            config = OrganizerConfig(
                target_directories=[target],
                archive_base=archive,
                dry_run=dry_run,
                use_recycle_bin=False,
            )
            config.excluded_dirs = self.DEFAULT_EXCLUDED.copy()

            organizer = FileOrganizer(config)

            try:
                # 1. 파일 스캔
                self._log("\n[1단계] 파일 스캔...")
                files = organizer.scan_directories()
                self._log(f"  스캔된 파일: {len(files):,}개")

                # 2. 중복 파일
                if self.include_duplicates.get():
                    self._log("\n[2단계] 중복 파일 탐지...")
                    duplicates = organizer.find_duplicates()
                    if duplicates:
                        summary = organizer.duplicate_finder.get_summary(duplicates)
                        self._log(f"  중복 그룹: {summary['duplicate_groups']}개")
                        self._log(f"  절약 가능: {summary['total_wasted_space_formatted']}")
                    else:
                        self._log("  중복 파일 없음")

                # 3. 버전 파일
                self._log("\n[3단계] 버전 파일 탐지...")
                versions = organizer.find_version_groups()
                self._log(f"  버전 그룹: {len(versions)}개")

                # 4. 분류
                if self.include_classify.get():
                    self._log("\n[4단계] 문서/이미지 분류...")
                    classify_files = [
                        f for f in files
                        if f.path.suffix.lower() in self.DEFAULT_CLASSIFY_EXT
                    ]
                    self._log(f"  분류 대상: {len(classify_files):,}개")

                    if classify_files:
                        classifications = organizer.classifier.classify_files(
                            classify_files, by_content=True, by_date=True
                        )

                        for result in classifications:
                            path_parts = [config.organized_archive, result.category]
                            if self.include_year.get() and result.year:
                                path_parts.append(str(result.year))
                            if self.include_month.get() and result.month:
                                path_parts.append(f"{result.month:02d}")
                            target_dir = Path(*[str(p) for p in path_parts])
                            result.target_path = target_dir / result.file_info.path.name

                        organizer._classifications = classifications

                        summary = organizer.classifier.get_classification_summary(classifications)
                        for cat, count in sorted(summary['by_category'].items(), key=lambda x: -x[1])[:5]:
                            self._log(f"    {cat}: {count}개")

                # 5. 계획
                self._log("\n[5단계] 정리 계획...")
                operations = organizer.plan_cleanup(
                    duplicates=self.include_duplicates.get(),
                    versions=False,
                    organize=self.include_classify.get(),
                    keep_strategy="newest"
                )
                self._log(f"  계획된 작업: {len(operations):,}개")

                # 6. 실행
                if operations:
                    self._log(f"\n[6단계] 실행...")
                    if dry_run:
                        report = organizer.get_dry_run_report()
                        for line in report.split('\n')[:30]:
                            self._log(line)
                    else:
                        results = organizer.execute(dry_run=False)
                        report = organizer.get_execution_report(results)
                        for line in report.split('\n'):
                            self._log(line)
                else:
                    self._log("\n처리할 작업이 없습니다.")

            finally:
                organizer.finalize()

            # 빈 폴더 정리
            if self.cleanup_empty.get() and not dry_run:
                self._log("\n[7단계] 빈 폴더 정리...")
                success, failed, _ = cleanup_empty_folders(
                    target, dry_run=False
                )
                self._log(f"  삭제된 빈 폴더: {success}개")

            self._log("\n" + "=" * 50)
            self._log("완료!")
            self._log("=" * 50)

        except Exception as e:
            self._log(f"\n오류 발생: {e}")

        finally:
            self.is_running = False
            self.root.after(0, self._on_complete)

    def _on_complete(self):
        """실행 완료 후 UI 업데이트"""
        self.run_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("완료")

    def _stop_organizer(self):
        """실행 중지"""
        self._log("\n중지 요청...")
        self.is_running = False

    def _open_restore(self):
        """복원 도구 열기"""
        restore_window = tk.Toplevel(self.root)
        restore_window.title("파일 복원")
        restore_window.geometry("600x400")

        ttk.Label(restore_window, text="복원 기능은 CLI를 사용해주세요:").pack(pady=20)
        ttk.Label(restore_window, text="python -m cli.restore").pack()

        ttk.Button(restore_window, text="닫기", command=restore_window.destroy).pack(pady=20)


def run_gui():
    """GUI 실행"""
    root = tk.Tk()
    app = FileOrganizerGUI(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()
