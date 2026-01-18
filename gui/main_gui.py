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
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog

# 상위 모듈 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import OrganizerConfig
from src.organizer import FileOrganizer
from src.llm_classifier import LLMConfig
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
        self.root.geometry("950x700")
        self.root.minsize(800, 500)

        # 상태 변수
        self.target_dir = tk.StringVar(value=str(Path.home() / "Downloads"))
        self.archive_dir = tk.StringVar(value=str(Path.home() / "_OrganizedFiles"))
        self.dry_run = tk.BooleanVar(value=True)
        self.include_duplicates = tk.BooleanVar(value=True)
        self.include_classify = tk.BooleanVar(value=True)
        self.include_year = tk.BooleanVar(value=True)
        self.include_month = tk.BooleanVar(value=False)
        self.cleanup_empty = tk.BooleanVar(value=True)

        # 제외 폴더 설정
        self.excluded_dirs = tk.StringVar()
        self._excluded_set = self.DEFAULT_EXCLUDED.copy()
        self._update_excluded_display()

        # LLM 설정
        self.llm_provider = tk.StringVar(value="none")
        self.llm_api_key = tk.StringVar()
        self.llm_model = tk.StringVar()

        # 작업 상태
        self.is_running = False
        self.message_queue = queue.Queue()
        self.preview_operations = []  # 미리보기 작업 저장

        self._create_widgets()
        self._start_message_handler()

    def _create_widgets(self):
        """위젯 생성"""
        # 메인 프레임 - 스크롤 가능하도록 설정
        main_container = ttk.Frame(self.root)
        main_container.grid(row=0, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_container.columnconfigure(0, weight=1)
        main_container.rowconfigure(0, weight=1)

        # 캔버스와 스크롤바
        canvas = tk.Canvas(main_container, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)
        main_container.rowconfigure(0, weight=1)

        main_frame = ttk.Frame(canvas, padding="10")
        canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

        def on_frame_configure(event=None):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def on_canvas_configure(event=None):
            canvas.itemconfig(canvas_window, width=event.width)

        main_frame.bind("<Configure>", on_frame_configure)
        canvas.bind("<Configure>", on_canvas_configure)
        main_frame.columnconfigure(0, weight=1)

        # === 폴더 설정 (행 0-1) ===
        folder_frame = ttk.LabelFrame(main_frame, text="📁 폴더 설정", padding="8")
        folder_frame.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        folder_frame.columnconfigure(1, weight=1)

        # 대상 폴더
        ttk.Label(folder_frame, text="대상:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(folder_frame, textvariable=self.target_dir).grid(row=0, column=1, sticky="ew", padx=5, pady=3)
        ttk.Button(folder_frame, text="찾아보기", width=10, command=self._browse_target).grid(row=0, column=2, padx=5, pady=3)

        # 저장 폴더
        ttk.Label(folder_frame, text="저장:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        ttk.Entry(folder_frame, textvariable=self.archive_dir).grid(row=1, column=1, sticky="ew", padx=5, pady=3)
        ttk.Button(folder_frame, text="찾아보기", width=10, command=self._browse_archive).grid(row=1, column=2, padx=5, pady=3)

        # === 제외 폴더 설정 (행 1) ===
        excluded_frame = ttk.LabelFrame(main_frame, text="🚫 제외 폴더", padding="8")
        excluded_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        excluded_frame.columnconfigure(0, weight=1)

        # 제외 폴더 표시
        excluded_display = ttk.Entry(excluded_frame, textvariable=self.excluded_dirs, state="readonly")
        excluded_display.grid(row=0, column=0, sticky="ew", padx=5, pady=3)

        # 버튼들 (한 줄로)
        excluded_btn_frame = ttk.Frame(excluded_frame)
        excluded_btn_frame.grid(row=1, column=0, sticky="w", padx=5, pady=(3, 0))

        ttk.Button(excluded_btn_frame, text="추가", width=8, command=self._add_excluded_dir).pack(side="left", padx=2)
        ttk.Button(excluded_btn_frame, text="제거", width=8, command=self._remove_excluded_dir).pack(side="left", padx=2)
        ttk.Button(excluded_btn_frame, text="초기화", width=8, command=self._reset_excluded_dirs).pack(side="left", padx=2)

        # === 정리 옵션 (행 2) ===
        option_frame = ttk.LabelFrame(main_frame, text="⚙️ 정리 옵션", padding="8")
        option_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        option_frame.columnconfigure(0, weight=1)
        option_frame.columnconfigure(1, weight=1)

        # 상단: 주요 옵션
        ttk.Checkbutton(option_frame, text="중복 파일 처리",
                        variable=self.include_duplicates).grid(row=0, column=0, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(option_frame, text="주제별 분류",
                        variable=self.include_classify).grid(row=0, column=1, sticky="w", padx=5, pady=2)

        # 중단: 날짜 옵션
        ttk.Checkbutton(option_frame, text="연도별 폴더",
                        variable=self.include_year).grid(row=1, column=0, sticky="w", padx=5, pady=2)
        ttk.Checkbutton(option_frame, text="월별 폴더",
                        variable=self.include_month).grid(row=1, column=1, sticky="w", padx=5, pady=2)

        # 하단: 정리 옵션
        ttk.Checkbutton(option_frame, text="빈 폴더 정리",
                        variable=self.cleanup_empty).grid(row=2, column=0, sticky="w", padx=5, pady=2)

        # === 실행 모드 (행 3) ===
        mode_frame = ttk.LabelFrame(main_frame, text="🎯 실행 모드", padding="8")
        mode_frame.grid(row=3, column=0, sticky="ew", pady=(0, 8))

        ttk.Radiobutton(mode_frame, text="미리보기 (드라이 런)",
                        variable=self.dry_run, value=True).pack(side="left", padx=10)
        ttk.Radiobutton(mode_frame, text="실제 실행",
                        variable=self.dry_run, value=False).pack(side="left", padx=10)

        # === 주요 버튼들 (행 4) ===
        main_button_frame = ttk.Frame(main_frame)
        main_button_frame.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        main_button_frame.columnconfigure(2, weight=1)  # 가운데 공간

        self.run_button = ttk.Button(main_button_frame, text="▶ 실행", command=self._run_organizer, width=10)
        self.run_button.pack(side="left", padx=3)

        self.stop_button = ttk.Button(main_button_frame, text="⏹ 중지", command=self._stop_organizer, state="disabled", width=10)
        self.stop_button.pack(side="left", padx=3)

        ttk.Button(main_button_frame, text="👁 미리보기", command=self._show_preview, width=12).pack(side="left", padx=3)

        # 우측 버튼
        ttk.Button(main_button_frame, text="🎯 Claude Code", command=self._show_claude_code_guide, width=14).pack(side="right", padx=3)
        ttk.Button(main_button_frame, text="🤖 LLM 설정", command=self._open_llm_settings, width=12).pack(side="right", padx=3)
        ttk.Button(main_button_frame, text="🔄 복원", command=self._open_restore, width=10).pack(side="right", padx=3)
        ttk.Button(main_button_frame, text="🗑 로그 지우기", command=self._clear_log, width=12).pack(side="right", padx=3)
        # === 로그 출력 (행 5) ===
        log_frame = ttk.LabelFrame(main_frame, text="📋 실행 로그", padding="8")
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(0, 8))
        main_frame.rowconfigure(5, weight=1)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state="disabled")

        # === 상태 바 (행 6) ===
        self.status_var = tk.StringVar(value="준비")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief="sunken")
        status_bar.grid(row=6, column=0, sticky="ew")

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

    def _update_excluded_display(self):
        """제외 폴더 표시 업데이트"""
        display = ", ".join(sorted(self._excluded_set))
        self.excluded_dirs.set(display)

    def _add_excluded_dir(self):
        """제외 폴더 추가"""
        dialog = tk.Toplevel(self.root)
        dialog.title("제외 폴더 추가")
        dialog.geometry("300x100")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="추가할 폴더명:").pack(pady=10, padx=10)
        entry = ttk.Entry(dialog, width=30)
        entry.pack(pady=5, padx=10)
        entry.focus()

        def add():
            folder = entry.get().strip()
            if folder:
                self._excluded_set.add(folder)
                self._update_excluded_display()
                messagebox.showinfo("성공", f"'{folder}'를 제외 목록에 추가했습니다.")
                dialog.destroy()

        ttk.Button(dialog, text="추가", command=add).pack(pady=10)

    def _remove_excluded_dir(self):
        """제외 폴더 제거"""
        if not self._excluded_set:
            messagebox.showinfo("알림", "제외할 폴더가 없습니다.")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("제외 폴더 제거")
        dialog.geometry("350x250")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="제거할 폴더 선택:").pack(pady=10, padx=10)

        # 리스트박스
        listbox = tk.Listbox(dialog)
        listbox.pack(fill="both", expand=True, padx=10, pady=5)

        for folder in sorted(self._excluded_set):
            listbox.insert("end", folder)

        def remove():
            selection = listbox.curselection()
            if selection:
                folder = listbox.get(selection[0])
                self._excluded_set.discard(folder)
                self._update_excluded_display()
                messagebox.showinfo("성공", f"'{folder}'를 제외 목록에서 제거했습니다.")
                dialog.destroy()
            else:
                messagebox.showwarning("경고", "제거할 폴더를 선택해주세요.")

        ttk.Button(dialog, text="제거", command=remove).pack(pady=10)

    def _reset_excluded_dirs(self):
        """제외 폴더 기본값 복원"""
        confirm = messagebox.askyesno("확인", "제외 폴더 목록을 기본값으로 복원하시겠습니까?")
        if confirm:
            self._excluded_set = self.DEFAULT_EXCLUDED.copy()
            self._update_excluded_display()
            messagebox.showinfo("완료", "제외 폴더 목록을 기본값으로 복원했습니다.")

    def _open_llm_settings(self):
        """LLM 설정 창 열기"""
        dialog = tk.Toplevel(self.root)
        dialog.title("🤖 LLM 분류 설정")
        dialog.geometry("600x450")
        dialog.transient(self.root)
        dialog.grab_set()

        # 프레임
        main = ttk.Frame(dialog, padding="15")
        main.pack(fill="both", expand=True)

        # 제공자 선택
        ttk.Label(main, text="LLM 제공자:").grid(row=0, column=0, sticky="w", pady=5)
        provider_combo = ttk.Combobox(main, textvariable=self.llm_provider, width=25,
                                     values=["none (키워드 기반)", "claude", "openai", "gemini", "ollama"],
                                     state="readonly")
        provider_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # API 키 (Claude, OpenAI, Gemini용)
        api_key_label = ttk.Label(main, text="API 키:")
        api_key_label.grid(row=1, column=0, sticky="w", pady=5)
        api_key_entry = ttk.Entry(main, textvariable=self.llm_api_key, width=30, show="*")
        api_key_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        # 모델 선택/입력
        model_label = ttk.Label(main, text="모델:")
        model_label.grid(row=2, column=0, sticky="w", pady=5)
        
        # 모델 콤보박스 (처음엔 Entry로)
        model_frame = ttk.Frame(main)
        model_frame.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        model_frame.columnconfigure(0, weight=1)
        
        model_entry = ttk.Entry(model_frame, textvariable=self.llm_model)
        model_entry.pack(side="left", fill="x", expand=True)
        
        # Ollama 모델 새로고침 버튼
        refresh_btn = ttk.Button(model_frame, text="🔄", width=3)
        refresh_btn.pack(side="left", padx=(5, 0))

        main.columnconfigure(1, weight=1)

        # Ollama 모델 목록 프레임 (처음엔 숨김)
        ollama_frame = ttk.LabelFrame(main, text="📦 사용 가능한 Ollama 모델", padding="10")
        ollama_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=10)
        ollama_frame.grid_remove()  # 숨김

        # 모델 리스트
        listbox_frame = ttk.Frame(ollama_frame)
        listbox_frame.pack(fill="both", expand=True)
        
        model_listbox = tk.Listbox(listbox_frame, height=6)
        model_listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=model_listbox.yview)
        scrollbar.pack(side="right", fill="y")
        model_listbox.config(yscrollcommand=scrollbar.set)

        # Ollama 버튼들
        ollama_btn_frame = ttk.Frame(ollama_frame)
        ollama_btn_frame.pack(fill="x", pady=(5, 0))
        
        def load_ollama_models():
            """Ollama 모델 목록 로드"""
            from src.llm_classifier import OllamaProvider
            models = OllamaProvider.list_models()
            model_listbox.delete(0, tk.END)
            if models:
                for model in models:
                    model_listbox.insert(tk.END, model)
                status_label.config(text=f"✓ {len(models)}개 모델 발견")
            else:
                status_label.config(text="⚠ Ollama가 실행되지 않았거나 모델이 없습니다")
        
        def select_model():
            """선택된 모델 적용"""
            selection = model_listbox.curselection()
            if selection:
                selected = model_listbox.get(selection[0])
                self.llm_model.set(selected)
                messagebox.showinfo("선택 완료", f"모델 '{selected}'이(가) 선택되었습니다.")
        
        def show_recommended_models():
            """추천 모델 목록 표시"""
            rec_dialog = tk.Toplevel(dialog)
            rec_dialog.title("📦 추천 모델")
            rec_dialog.geometry("500x400")
            rec_dialog.transient(dialog)
            rec_dialog.grab_set()
            
            frame = ttk.Frame(rec_dialog, padding="10")
            frame.pack(fill="both", expand=True)
            
            ttk.Label(frame, text="다운로드할 모델을 선택하세요:", font=("", 10, "bold")).pack(pady=5)
            
            # 추천 모델 목록
            recommended = [
                ("gemini-3-flash-preview:cloud", "Gemini Flash (빠름, 클라우드)"),
                ("gemini-3-pro-preview:latest", "Gemini Pro (강력함, 클라우드)"),
                ("deepseek-v3.1:671b-cloud", "DeepSeek V3.1 (671B, 클라우드)"),
                ("deepseek-v3.2:cloud", "DeepSeek V3.2 (최신, 클라우드)"),
                ("qwen3-coder:480b-cloud", "Qwen3 Coder (480B, 코딩 특화)"),
                ("glm-4.6:cloud", "GLM-4.6 (클라우드)"),
                ("cogito-2.1:671b-cloud", "Cogito 2.1 (671B, 클라우드)"),
                ("llama3.2", "Llama 3.2 (메타, 범용)"),
                ("mistral", "Mistral (빠름, 효율적)"),
                ("qwen2.5:7b", "Qwen 2.5 7B (경량)"),
            ]
            
            rec_listbox = tk.Listbox(frame, height=12)
            rec_listbox.pack(fill="both", expand=True, pady=5)
            
            for model, desc in recommended:
                rec_listbox.insert(tk.END, f"{model} - {desc}")
            
            btn_frame = ttk.Frame(frame)
            btn_frame.pack(pady=5)
            
            def download_selected():
                selection = rec_listbox.curselection()
                if selection:
                    selected = rec_listbox.get(selection[0])
                    model_name = selected.split(" - ")[0]
                    rec_dialog.destroy()
                    start_download(model_name)
                else:
                    messagebox.showwarning("선택 필요", "다운로드할 모델을 선택해주세요.")
            
            ttk.Button(btn_frame, text="다운로드", command=download_selected).pack(side="left", padx=5)
            ttk.Button(btn_frame, text="취소", command=rec_dialog.destroy).pack(side="left", padx=5)
        
        def start_download(model_name):
            """모델 다운로드 시작"""
            from src.llm_classifier import OllamaProvider
            status_label.config(text=f"⏳ '{model_name}' 다운로드 중...")
            dialog.update()
            
            # 백그라운드에서 다운로드
            import threading
            def download():
                success = OllamaProvider.pull_model(model_name)
                dialog.after(0, lambda: on_download_complete(success, model_name))
            
            def on_download_complete(success, name):
                if success:
                    status_label.config(text=f"✓ '{name}' 다운로드 완료!")
                    load_ollama_models()
                else:
                    status_label.config(text=f"✗ '{name}' 다운로드 실패")
            
            threading.Thread(target=download, daemon=True).start()
        
        def pull_model():
            """새 모델 다운로드"""
            # 추천 모델 표시 또는 직접 입력
            choice = messagebox.askquestion(
                "모델 다운로드",
                "추천 모델 목록에서 선택하시겠습니까?\n\n'아니오'를 선택하면 모델명을 직접 입력할 수 있습니다.",
                parent=dialog
            )
            
            if choice == "yes":
                show_recommended_models()
            else:
                model_name = tk.simpledialog.askstring(
                    "모델 다운로드",
                    "다운로드할 모델명을 입력하세요:\n(예: llama3.2, mistral, qwen2.5:7b)",
                    parent=dialog
                )
                if model_name:
                    start_download(model_name)
        
        ttk.Button(ollama_btn_frame, text="모델 선택", command=select_model).pack(side="left", padx=2)
        ttk.Button(ollama_btn_frame, text="추천 모델 다운로드", command=pull_model).pack(side="left", padx=2)
        
        status_label = ttk.Label(ollama_frame, text="")
        status_label.pack(pady=(5, 0))

        # 제공자 변경 시 UI 업데이트
        def on_provider_change(*args):
            provider = self.llm_provider.get().split()[0]
            
            if provider == "ollama":
                # Ollama 선택 시
                api_key_label.config(state="disabled")
                api_key_entry.config(state="disabled")
                refresh_btn.config(state="normal", command=load_ollama_models)
                ollama_frame.grid()  # 표시
                load_ollama_models()  # 자동 로드
            else:
                # 다른 제공자 선택 시
                api_key_label.config(state="normal")
                api_key_entry.config(state="normal")
                refresh_btn.config(state="disabled")
                ollama_frame.grid_remove()  # 숨김
        
        self.llm_provider.trace_add("write", on_provider_change)
        on_provider_change()  # 초기 설정

        # 도움말
        help_text = """
🔸 none: LLM 없이 키워드 기반 분류 (빠름, 무료)
🔸 claude: Anthropic Claude (API 키 필요, 정확함)
🔸 openai: OpenAI GPT (API 키 필요, 빠름)
🔸 gemini: Google Gemini (API 키 필요, 저렴함)
🔸 ollama: 로컬 LLM (무료, 오프라인, API 키 불필요)

💡 Ollama 사용 시:
1. Ollama 설치: https://ollama.ai/download
2. 터미널에서 실행: ollama serve
3. 이 창에서 모델 선택 또는 다운로드
        """
        help_label = ttk.Label(main, text=help_text, justify="left",
                              relief="groove", padding=10, font=("", 9))
        help_label.grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)

        # 버튼
        btn_frame = ttk.Frame(main)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)

        def save():
            provider = self.llm_provider.get().split()[0]
            model = self.llm_model.get() or "(기본값)"
            messagebox.showinfo("저장", f"LLM 설정이 저장되었습니다.\n제공자: {provider}\n모델: {model}")
            dialog.destroy()

        ttk.Button(btn_frame, text="저장", width=12, command=save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="취소", width=12, command=dialog.destroy).pack(side="left", padx=5)

    def _log(self, message: str):
        """로그 메시지 큐에 추가"""
        self.message_queue.put(message)

    def _get_llm_config(self) -> Optional[LLMConfig]:
        """현재 LLM 설정 반환"""
        provider = self.llm_provider.get().split()[0]  # "none (키워드 기반)" → "none"
        
        if provider == "none":
            return None
        
        api_key = self.llm_api_key.get() or None
        model = self.llm_model.get() or None
        
        return LLMConfig(
            provider=provider,
            api_key=api_key,
            model=model
        )

    def _show_preview(self):
        """미리보기 창 표시"""
        if self.is_running:
            messagebox.showwarning("경고", "작업 진행 중입니다. 먼저 작업을 중지해주세요.")
            return

        # 경로 검증
        target = Path(self.target_dir.get())
        if not target.exists():
            messagebox.showerror("오류", f"대상 폴더가 존재하지 않습니다:\n{target}")
            return

        # 백그라운드에서 미리보기 수집
        self.run_button.config(state="disabled")
        self.status_var.set("미리보기 생성 중...")

        thread = threading.Thread(target=self._collect_preview, daemon=True)
        thread.start()

    def _collect_preview(self):
        """미리보기 데이터 수집"""
        try:
            target = Path(self.target_dir.get())
            archive = Path(self.archive_dir.get())

            # 설정 생성
            config = OrganizerConfig(
                target_directories=[target],
                archive_base=archive,
                dry_run=True,
                use_recycle_bin=False,
            )
            config.excluded_dirs = self._excluded_set.copy()

            # LLM 설정
            llm_config = self._get_llm_config()

            organizer = FileOrganizer(config, llm_config=llm_config)

            # 파일 스캔
            files = organizer.scan_directories()

            # 중복 파일 정보를 먼저 수집
            duplicates = []
            if self.include_duplicates.get():
                duplicates = organizer.find_duplicates()

            # 분류 정보 수집 (중복 제외 후 진행)
            classifications = []
            if self.include_classify.get():
                classify_files = [
                    f for f in files
                    if f.path.suffix.lower() in self.DEFAULT_CLASSIFY_EXT
                ]

                if classify_files:
                    classifications = organizer.classify_files(
                        classify_files, by_content=True, by_date=True, exclude_duplicates=True, keep_strategy="newest"
                    )

                    for result in classifications:
                        path_parts = [config.organized_archive, result.category]
                        if self.include_year.get() and result.year:
                            path_parts.append(str(result.year))
                        if self.include_month.get() and result.month:
                            path_parts.append(f"{result.month:02d}")
                        target_dir = Path(*[str(p) for p in path_parts])
                        result.target_path = target_dir / result.file_info.path.name

            # 미리보기 창 표시
            self.root.after(0, lambda: self._show_preview_window(
                files, classifications, duplicates, config
            ))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("오류", f"미리보기 생성 실패:\n{e}"))

        finally:
            self.root.after(0, lambda: self.run_button.config(state="normal"))
            self.root.after(0, lambda: self.status_var.set("준비"))

    def _show_preview_window(self, files, classifications, duplicates, config):
        """미리보기 창 생성 및 표시"""
        preview_window = tk.Toplevel(self.root)
        preview_window.title("파일 정리 미리보기")
        preview_window.geometry("900x600")

        # 탭 생성
        notebook = ttk.Notebook(preview_window)
        notebook.pack(fill="both", expand=True, padx=5, pady=5)

        # 탭1: 분류 미리보기
        if classifications:
            class_frame = ttk.Frame(notebook)
            notebook.add(class_frame, text=f"분류 예정 파일 ({len(classifications)}개)")

            tree = ttk.Treeview(
                class_frame,
                columns=("파일명", "현재위치", "이동예정경로", "카테고리"),
                height=20
            )
            tree.column("#0", width=0, stretch=tk.NO)
            tree.column("파일명", width=150)
            tree.column("현재위치", width=250)
            tree.column("이동예정경로", width=250)
            tree.column("카테고리", width=100)

            tree.heading("#0", text="")
            tree.heading("파일명", text="파일명")
            tree.heading("현재위치", text="현재 위치")
            tree.heading("이동예정경로", text="이동 예정 경로")
            tree.heading("카테고리", text="카테고리")

            for idx, result in enumerate(classifications[:100]):
                file_info = result.file_info
                target_path = result.target_path if hasattr(result, 'target_path') else "미정"
                tree.insert("", "end", text=str(idx+1), values=(
                    file_info.path.name,
                    str(file_info.path.parent),
                    str(target_path.parent) if target_path != "미정" else "미정",
                    result.category
                ))

            scrollbar = ttk.Scrollbar(class_frame, orient="vertical", command=tree.yview)
            tree.configure(yscroll=scrollbar.set)

            tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            scrollbar.pack(side="right", fill="y", pady=5)

            # 통계
            stats_text = f"분류될 파일: {len(classifications)}개"
            ttk.Label(class_frame, text=stats_text, relief="sunken").pack(fill="x", padx=5, pady=(0, 5))

        # 탭2: 중복 파일
        if duplicates:
            dup_frame = ttk.Frame(notebook)
            notebook.add(dup_frame, text=f"중복 파일 ({len(duplicates)}개 그룹)")

            tree = ttk.Treeview(
                dup_frame,
                columns=("파일명", "위치", "크기"),
                height=20
            )
            tree.column("#0", width=30, stretch=tk.NO)
            tree.column("파일명", width=200)
            tree.column("위치", width=350)
            tree.column("크기", width=80)

            tree.heading("#0", text="그룹")
            tree.heading("파일명", text="파일명")
            tree.heading("위치", text="위치")
            tree.heading("크기", text="크기")

            for group_idx, group in enumerate(duplicates[:50]):
                parent = tree.insert("", "end", text=f"G{group_idx+1}", values=("", "", ""))
                for file_info in group.files[:10]:
                    size_mb = file_info.size / (1024 * 1024)
                    tree.insert(parent, "end", text="", values=(
                        file_info.path.name,
                        str(file_info.path.parent),
                        f"{size_mb:.1f} MB"
                    ))

            scrollbar = ttk.Scrollbar(dup_frame, orient="vertical", command=tree.yview)
            tree.configure(yscroll=scrollbar.set)

            tree.pack(side="left", fill="both", expand=True, padx=5, pady=5)
            scrollbar.pack(side="right", fill="y", pady=5)

            # 통계
            total_dup_size = sum(
                min(f.size for f in group.files) * (len(group.files) - 1)
                for group in duplicates
            )
            size_mb = total_dup_size / (1024 * 1024)
            stats_text = f"중복 그룹: {len(duplicates)}개 | 절약 가능: {size_mb:.1f} MB"
            ttk.Label(dup_frame, text=stats_text, relief="sunken").pack(fill="x", padx=5, pady=(0, 5))

        # 탭3: 종합 통계
        stats_frame = ttk.Frame(notebook)
        notebook.add(stats_frame, text="종합 통계")

        summary_text = f"""
파일 정리 미리보기 요약

【스캔 결과】
- 전체 파일: {len(files):,}개

【분류 대상 (예정)】
- 분류될 파일: {len(classifications)}개
- 주요 카테고리:
"""
        if classifications:
            categories = {}
            for result in classifications:
                categories[result.category] = categories.get(result.category, 0) + 1

            for cat, count in sorted(categories.items(), key=lambda x: -x[1])[:10]:
                summary_text += f"  • {cat}: {count}개\n"

        summary_text += f"""
【중복 파일 (예정)】
- 중복 그룹: {len(duplicates)}개
"""
        if duplicates:
            total_dup_size = sum(
                min(f.size for f in group.files) * (len(group.files) - 1)
                for group in duplicates
            )
            size_mb = total_dup_size / (1024 * 1024)
            summary_text += f"- 절약 가능: {size_mb:.1f} MB\n"

        summary_text += f"""
【설정】
- 대상 폴더: {self.target_dir.get()}
- 저장 폴더: {self.archive_dir.get()}
- 제외 폴더: {', '.join(sorted(self._excluded_set))}
"""

        text_widget = scrolledtext.ScrolledText(stats_frame, wrap=tk.WORD, height=25)
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert("1.0", summary_text)
        text_widget.config(state="disabled")

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
            config.excluded_dirs = self._excluded_set.copy()

            # LLM 설정
            llm_config = self._get_llm_config()

            organizer = FileOrganizer(config, llm_config=llm_config)

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

                    # LLM 사용 여부 표시
                    llm_config = self._get_llm_config()
                    if llm_config and llm_config.provider != "none":
                        self._log(f"  📡 LLM 분류 활성화: {llm_config.provider}")
                        self._log(f"  ⚠️ LLM 분류는 시간이 오래 걸릴 수 있습니다...")
                    else:
                        self._log(f"  🔤 키워드 기반 분류 (빠름)")

                    if classify_files:
                        classifications = organizer.classify_files(
                            classify_files, by_content=True, by_date=True, exclude_duplicates=True, keep_strategy="newest"
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

    def _show_claude_code_guide(self):
        """Claude Code 모드 가이드 표시"""
        guide_window = tk.Toplevel(self.root)
        guide_window.title("🎯 Claude Code로 정확한 파일 분류")
        guide_window.geometry("700x600")
        guide_window.transient(self.root)

        main_frame = ttk.Frame(guide_window, padding="20")
        main_frame.pack(fill="both", expand=True)

        # 제목
        title_label = ttk.Label(main_frame, text="Claude Code로 정확한 파일 분류하기",
                               font=("", 14, "bold"))
        title_label.pack(pady=(0, 10))

        # 설명 텍스트
        guide_text = """
🎯 Claude Code란?

Claude AI와 실시간으로 협업하여 파일을 분류하는 방식입니다.
단순 자동화가 아닌, AI와 대화하며 맞춤형 분류 규칙을 적용합니다.

📊 분류 모드 비교

┌─────────────┬────────┬──────────┬─────────────┐
│   방식      │  속도  │  정확도  │  적합한 경우  │
├─────────────┼────────┼──────────┼─────────────┤
│ 확장자 기반 │ ⚡⚡⚡  │    ⭐   │  단순 정리   │
│ LLM 자동    │   🐌   │  ⭐⭐⭐  │ 50개 이하   │
│ Claude Code │ ⚡⚡⚡  │ ⭐⭐⭐⭐⭐ │ 대량/정확함 │
└─────────────┴────────┴──────────┴─────────────┘

💡 Claude Code의 장점

✓ 파일 내용을 직접 읽고 분석
✓ 대화로 분류 규칙 조정 가능
✓ 프로젝트 구조 이해
✓ 대량 파일도 빠르게 처리
✓ 복잡한 조건부 분류 가능

📝 사용 예시

1. 업무 문서 정리
   "Downloads 폴더의 문서를 정리해줘.
    송장은 '재무/송장'으로, 계약서는 '법무'로 분류해."

2. 사진 정리
   "사진을 정리하되, 스크린샷은 별도 폴더로,
    가족 사진은 연도별로 분류해줘."

3. 개발 프로젝트
   "코드 파일을 프로젝트별로 정리하고,
    README는 각 프로젝트 폴더 내 docs로 이동해."

🚀 시작하기

1. VSCode에서 Claude Code Extension 설치
   또는 CLI: npm install -g @anthropic-ai/claude-code

2. 이 프로젝트 폴더에서 실행:
   - VSCode: Ctrl+Shift+P → "Claude Code: Start"
   - CLI: claude-code

3. Claude에게 요청:
   "파일을 분류해줘. [여기에 요구사항 입력]"

📚 자세한 가이드: CLAUDE_CODE_MODE.md 참고
"""

        text_widget = scrolledtext.ScrolledText(main_frame, wrap=tk.WORD, height=25,
                                               font=("Consolas", 9))
        text_widget.pack(fill="both", expand=True, pady=10)
        text_widget.insert("1.0", guide_text)
        text_widget.config(state="disabled")

        # 버튼
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill="x", pady=(10, 0))

        def open_guide_file():
            """가이드 파일 열기"""
            import subprocess
            import sys
            guide_path = Path(__file__).parent.parent / "CLAUDE_CODE_MODE.md"
            if guide_path.exists():
                if sys.platform == "win32":
                    subprocess.run(["start", "", str(guide_path)], shell=True)
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(guide_path)])
                else:
                    subprocess.run(["xdg-open", str(guide_path)])
            else:
                messagebox.showinfo("알림", "가이드 파일을 찾을 수 없습니다.")

        ttk.Button(btn_frame, text="📖 전체 가이드 보기", command=open_guide_file).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="닫기", command=guide_window.destroy).pack(side="right", padx=5)

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
