import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from tkinter.simpledialog import askstring


class PackagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("RNX 高级打包工具 (虚拟环境支持版)")
        self.root.geometry("900x700")
        
        # 存储虚拟环境路径和类型
        self.venv_paths = []  # 格式: [(name, path, type), ...]
        self.current_venv = None
        self.icon_path = ""

        self.create_widgets()
        self.detect_virtualenvs()

    def create_widgets(self):
        """创建所有界面控件"""
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 基础配置标签页
        tab_basic = ttk.Frame(notebook)
        self.create_basic_tab(tab_basic)
        notebook.add(tab_basic, text="基础配置")

        # 高级配置标签页
        tab_advanced = ttk.Frame(notebook)
        self.create_advanced_tab(tab_advanced)
        notebook.add(tab_advanced, text="高级配置")

        # 日志输出
        self.log_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=120, height=20)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_area.configure(state='disabled')

        # 开始按钮
        ttk.Button(self.root, text="开始打包", command=self.start_packaging).pack(pady=10)

    def log_output(self, message):
        """实时输出日志"""
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.configure(state='disabled')
        self.log_area.see(tk.END)
        self.root.update()

    def create_basic_tab(self, parent):
        """基础配置标签页"""
        frame = ttk.LabelFrame(parent, text="基本参数")
        frame.pack(fill=tk.BOTH, padx=10, pady=10, expand=True)

        # 虚拟环境选择
        ttk.Label(frame, text="虚拟环境:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.cb_venv = ttk.Combobox(frame, width=50, state="readonly")
        self.cb_venv.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(frame, text="刷新", command=self.detect_virtualenvs).grid(row=0, column=2, padx=5, pady=5)

        # 项目路径
        ttk.Label(frame, text="项目根目录:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.entry_project = ttk.Entry(frame, width=50)
        self.entry_project.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(frame, text="浏览...", command=lambda: self.browse_path(self.entry_project)).grid(row=1, column=2, padx=5, pady=5)

        # 主脚本路径
        ttk.Label(frame, text="主脚本路径:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.entry_main_script = ttk.Entry(frame, width=50)
        self.entry_main_script.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(frame, text="浏览...", command=lambda: self.browse_file(self.entry_main_script)).grid(row=2, column=2, padx=5, pady=5)

        # 输出目录
        ttk.Label(frame, text="输出目录:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.entry_output = ttk.Entry(frame, width=50)
        self.entry_output.grid(row=3, column=1, padx=5, pady=5)
        ttk.Button(frame, text="浏览...", command=lambda: self.browse_path(self.entry_output)).grid(row=3, column=2, padx=5, pady=5)

        # 程序名称
        ttk.Label(frame, text="程序名称:").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        self.entry_app_name = ttk.Entry(frame, width=50)
        self.entry_app_name.grid(row=4, column=1, padx=5, pady=5)
        self.entry_app_name.insert(0, "RNX_Demo")

        # 图标文件
        ttk.Label(frame, text="程序图标:").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        self.entry_icon = ttk.Entry(frame, width=50)
        self.entry_icon.grid(row=5, column=1, padx=5, pady=5)
        ttk.Button(frame, text="浏览...", command=self.load_icon).grid(row=5, column=2, padx=5, pady=5)

        # 打包模式
        ttk.Label(frame, text="打包模式:").grid(row=6, column=0, padx=5, pady=5, sticky="e")
        self.var_mode = tk.StringVar(value="onefile")
        ttk.Radiobutton(frame, text="单文件", variable=self.var_mode, value="onefile").grid(row=6, column=1, sticky="w")
        ttk.Radiobutton(frame, text="多文件", variable=self.var_mode, value="onedir").grid(row=6, column=1, sticky="e")

    def create_advanced_tab(self, parent):
        """高级配置标签页"""
        frame = ttk.LabelFrame(parent, text="高级参数")
        frame.pack(fill=tk.BOTH, padx=10, pady=10, expand=True)

        # UPX压缩
        self.var_upx = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="启用UPX压缩", variable=self.var_upx).grid(row=0, column=0, padx=5, pady=5, sticky="w")

        # 控制台窗口
        self.var_console = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="显示控制台", variable=self.var_console).grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 隐藏导入模块
        ttk.Label(frame, text="隐藏导入模块:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.list_hidden_imports = tk.Listbox(frame, width=50, height=5)
        self.list_hidden_imports.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(frame, text="添加", command=self.add_hidden_import).grid(row=1, column=2, padx=5, pady=5)

        # 额外数据文件
        ttk.Label(frame, text="额外数据文件:").grid(row=2, column=0, padx=5, pady=5, sticky="ne")
        self.tree_data = ttk.Treeview(frame, columns=("src", "dest"), height=5, show="headings")
        self.tree_data.heading("src", text="源路径")
        self.tree_data.heading("dest", text="目标路径")
        self.tree_data.column("src", width=200)
        self.tree_data.column("dest", width=200)
        self.tree_data.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(frame, text="添加", command=self.add_data_file).grid(row=2, column=2, padx=5, pady=5)

    # --------------------------
    # 核心功能方法
    # --------------------------
    def detect_virtualenvs(self):
        """检测所有可用的虚拟环境"""
        self.venv_paths = []
        
        # 1. 检测项目目录下的 venv
        project_dir = self.entry_project.get() if self.entry_project.get() else os.getcwd()
        for venv_name in ["venv", ".venv", "env"]:
            venv_path = os.path.join(project_dir, venv_name)
            if os.path.exists(venv_path):
                self.venv_paths.append((f"本地 {venv_name}", venv_path, "venv"))

        # 2. 检测 conda 环境
        try:
            result = subprocess.run("conda env list --json", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                import json
                envs = json.loads(result.stdout)["envs"]
                for env_path in envs:
                    env_name = os.path.basename(env_path)
                    self.venv_paths.append((f"Conda: {env_name}", env_path, "conda"))
        except:
            pass

        # 更新下拉框
        self.cb_venv["values"] = [name for name, _, _ in self.venv_paths]
        if self.venv_paths:
            self.cb_venv.current(0)

    def get_activate_command(self, venv_info):
        """生成虚拟环境激活命令"""
        name, path, venv_type = venv_info
        if venv_type == "conda":
            return f"conda activate {os.path.basename(path)}"
        else:
            if sys.platform == "win32":
                return f"call {os.path.join(path, 'Scripts', 'activate')}"
            else:
                return f"source {os.path.join(path, 'bin', 'activate')}"

    def start_packaging(self):
        try:
            # 生成.spec文件（已包含所有配置）
            spec_content = self.generate_spec_content()
            spec_path = os.path.join(self.entry_project.get(), "temp.spec")
            with open(spec_path, "w") as f:
                f.write(spec_content)
            self.log_output(f">>> 已生成spec文件: {spec_path}")

            # 构建基础命令（不再包含冲突参数）
            cmd = [
                "pyinstaller",
                spec_path,
                "--distpath", self.entry_output.get(),
                "--workpath", os.path.join(self.entry_output.get(), "build")
            ]

            # 虚拟环境激活
            venv_index = self.cb_venv.current()
            if venv_index >= 0 and self.venv_paths:
                venv_info = self.venv_paths[venv_index]
                activate_cmd = self.get_activate_command(venv_info)
                full_cmd = f"{activate_cmd} && {' '.join(cmd)}"
            else:
                full_cmd = " ".join(cmd)

            self.log_output(f">>> 执行命令: {full_cmd}")

            # 执行打包
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                shell=True
            )
            for line in process.stdout:
                self.log_output(line.strip())
                self.root.update()

            if process.wait() == 0:
                self.log_output(">>> 打包成功！")
                messagebox.showinfo("完成", "打包成功！")
            else:
                self.log_output(">>> 打包失败！")
                messagebox.showerror("错误", "打包过程中出现错误！")

        except Exception as e:
            self.log_output(f">>> 发生异常: {str(e)}")
            messagebox.showerror("异常", f"打包失败:\n{str(e)}")


    # --------------------------
    # 辅助方法
    # --------------------------
    def browse_path(self, entry_widget):
        path = filedialog.askdirectory()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)
            if entry_widget == self.entry_project:
                self.detect_virtualenvs()  # 项目路径变化时重新检测虚拟环境

    def browse_file(self, entry_widget):
        path = filedialog.askopenfilename()
        if path:
            entry_widget.delete(0, tk.END)
            entry_widget.insert(0, path)

    def load_icon(self):
        path = filedialog.askopenfilename(filetypes=[("ICO files", "*.ico"), ("All files", "*.*")])
        if path:
            self.entry_icon.delete(0, tk.END)
            self.entry_icon.insert(0, path)
            self.icon_path = path

    def add_hidden_import(self):
        module = askstring("添加模块", "请输入模块名（如 'widgets.AutoFontSizeComboBox'）:")
        if module:
            self.list_hidden_imports.insert(tk.END, module)

    def add_data_file(self):
        src = filedialog.askdirectory() or filedialog.askopenfilename()
        if src:
            dest = askstring("目标路径", "指定打包后的相对路径（如 'resources'）:", initialvalue="")
            if dest:
                self.tree_data.insert("", tk.END, values=(src, dest))

    def generate_spec_content(self):
        return f"""# -*- mode: python -*-
        block_cipher = None

        a = Analysis(
            ['{self.entry_main_script.get()}'],
            pathex=['{self.entry_project.get()}'],
            binaries=[],
            datas={self.get_data_files()},
            hiddenimports={self.get_hidden_imports()},
            hookspath=[],
            runtime_hooks=[],
            excludes=[],
            win_no_prefer_redirects=False,
            win_private_assemblies=False,
            cipher=block_cipher,
            noarchive=False,
        )
        pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

        exe = EXE(
            pyz,
            a.scripts,
            a.binaries,
            a.zipfiles,
            a.datas,
            name='{self.entry_app_name.get()}',
            debug=False,
            {'console=True' if self.var_console.get() else 'console=False'},
            {'upx=True' if self.var_upx.get() else 'upx=False'},
            {'onefile=True' if self.var_mode.get() == 'onefile' else 'onefile=False'},
            icon=r'{self.icon_path}' if self.icon_path else None,
        )
    """



    def get_hidden_imports(self):
        return [self.list_hidden_imports.get(i) for i in range(self.list_hidden_imports.size())]

    def get_data_files(self):
        return [(self.tree_data.item(i)["values"][0], self.tree_data.item(i)["values"][1]) 
                for i in self.tree_data.get_children()]
    
    


if __name__ == "__main__":
    root = tk.Tk()
    app = PackagerApp(root)
    root.mainloop()
