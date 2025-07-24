import os
import sys
import subprocess
import json
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
        
        # 配置文件路径
        self.config_file = os.path.join(os.path.expanduser("~"), ".rnx_packager_config.json")
 
        self.create_widgets()
        self.detect_virtualenvs()
        self.load_config()  # 加载上次的配置

    def create_widgets(self):
        """创建所有界面控件"""
        # 虚拟环境选择
        ttk.Label(self.root, text="虚拟环境:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.cb_venv = ttk.Combobox(self.root, width=50, state="readonly")
        self.cb_venv.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(self.root, text="刷新", command=self.detect_virtualenvs).grid(row=0, column=2, padx=5, pady=5)

        # 项目路径
        ttk.Label(self.root, text="项目根目录:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.entry_project = ttk.Entry(self.root, width=50)
        self.entry_project.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="浏览...", command=self.browse_project).grid(row=1, column=2, padx=5, pady=5)

        # 输出目录
        ttk.Label(self.root, text="输出目录:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.entry_output = ttk.Entry(self.root, width=50)
        self.entry_output.grid(row=2, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="浏览...", command=self.browse_output).grid(row=2, column=2, padx=5, pady=5)

        # 程序名称
        ttk.Label(self.root, text="程序名称:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.entry_app_name = ttk.Entry(self.root, width=50)
        self.entry_app_name.grid(row=3, column=1, padx=5, pady=5)
        self.entry_app_name.insert(0, "RNX_Demo")

        # 打包选项
        self.var_onefile = tk.BooleanVar(value=True)
        self.var_console = tk.BooleanVar(value=False)
        self.var_upx = tk.BooleanVar(value=True)
        
        ttk.Checkbutton(self.root, text="单文件模式", variable=self.var_onefile).grid(row=4, column=1, sticky="w")
        ttk.Checkbutton(self.root, text="显示控制台", variable=self.var_console).grid(row=5, column=1, sticky="w")
        ttk.Checkbutton(self.root, text="使用 UPX 压缩", variable=self.var_upx).grid(row=6, column=1, sticky="w")

        # 底部按钮框架
        button_frame = ttk.Frame(self.root)

        
        # 保存配置按钮
        ttk.Button(button_frame, text="保存配置", command=self.save_config).pack(side=tk.LEFT, padx=5)

        # 开始按钮
        ttk.Button(self.root, text="开始打包", command=self.start_packaging).grid(row=7, column=1, pady=10)

        # 日志输出
        self.log_area = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=100, height=25)
        self.log_area.grid(row=8, column=0, columnspan=3, padx=10, pady=10)
        self.log_area.configure(state='disabled')

    def save_config(self):
        """保存当前配置到文件"""
        config = {
            "project_path": self.entry_project.get(),
            "main_script": self.entry_main_script.get(),
            "output_path": self.entry_output.get(),
            "app_name": self.entry_app_name.get(),
            "icon_path": self.entry_icon.get(),
            "mode": self.var_mode.get(),
            "upx": self.var_upx.get(),
            "console": self.var_console.get(),
            "hidden_imports": [self.list_hidden_imports.get(i) for i in range(self.list_hidden_imports.size())],
            "data_files": [self.tree_data.item(i)["values"] for i in self.tree_data.get_children()],
            "venv_index": self.cb_venv.current()
        }
        
        try:
            with open(self.config_file, "w") as f:
                json.dump(config, f, indent=4)
            self.log_output(">>> 配置已保存")
            messagebox.showinfo("成功", "配置已保存到配置文件")
        except Exception as e:
            self.log_output(f">>> 保存配置失败: {str(e)}")
            messagebox.showerror("错误", f"保存配置失败:\n{str(e)}")
 
    def load_config(self):
        """从文件加载配置"""
        if not os.path.exists(self.config_file):
            return
            
        try:
            with open(self.config_file, "r") as f:
                config = json.load(f)
                
            # 加载基础配置
            self.entry_project.delete(0, tk.END)
            self.entry_project.insert(0, config.get("project_path", ""))
            
            self.entry_main_script.delete(0, tk.END)
            self.entry_main_script.insert(0, config.get("main_script", ""))
            
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, config.get("output_path", ""))
            
            self.entry_app_name.delete(0, tk.END)
            self.entry_app_name.insert(0, config.get("app_name", "RNX_Demo"))
            
            self.entry_icon.delete(0, tk.END)
            self.entry_icon.insert(0, config.get("icon_path", ""))
            self.icon_path = config.get("icon_path", "")
            
            self.var_mode.set(config.get("mode", "onefile"))
            self.var_upx.set(config.get("upx", True))
            self.var_console.set(config.get("console", False))
            
            # 加载高级配置
            self.list_hidden_imports.delete(0, tk.END)
            for module in config.get("hidden_imports", []):
                self.list_hidden_imports.insert(tk.END, module)
                
            self.tree_data.delete(*self.tree_data.get_children())
            for src, dest in config.get("data_files", []):
                self.tree_data.insert("", tk.END, values=(src, dest))
            
            # 设置虚拟环境选择
            venv_index = config.get("venv_index", -1)
            if venv_index >= 0 and venv_index < len(self.venv_paths):
                self.cb_venv.current(venv_index)
                
            self.log_output(">>> 配置已从文件加载")
        except Exception as e:
            self.log_output(f">>> 加载配置失败: {str(e)}")

    def detect_virtualenvs(self):
        """自动检测虚拟环境"""
        self.venv_paths = []
        
        # 检测当前目录下的 venv
        for venv_name in ["venv", ".venv", "env"]:
            venv_path = os.path.abspath(venv_name)
            if os.path.exists(venv_path):
                self.venv_paths.append((f"本地 {venv_name}", venv_path))

        # 检测 conda 环境
        try:
            conda_envs = subprocess.check_output("conda env list", shell=True, text=True).splitlines()
            for line in conda_envs:
                if line.strip() and not line.startswith("#"):
                    parts = line.split()
                    if len(parts) >= 2:
                        env_name = parts[0]
                        env_path = parts[-1]
                        print(env_name, env_path)
                        if os.path.exists(env_path):
                            self.venv_paths.append((f"Conda: {env_name}", env_path))
        except:
            pass

        # 更新下拉框
        self.cb_venv["values"] = [name for name, _ in self.venv_paths]
        if self.venv_paths:
            self.cb_venv.current(0)

    def browse_project(self):
        """选择项目目录"""
        path = filedialog.askdirectory(title="选择项目根目录")
        if path:
            self.entry_project.delete(0, tk.END)
            self.entry_project.insert(0, path)
            # 自动检测项目内的虚拟环境
            self.detect_virtualenvs()

    def browse_output(self):
        """选择输出目录"""
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.entry_output.delete(0, tk.END)
            self.entry_output.insert(0, path)

    def log_output(self, message):
        """实时输出日志"""
        self.log_area.configure(state='normal')
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.configure(state='disabled')
        self.log_area.see(tk.END)
        self.root.update()

    def get_activate_command(self, venv_path):
        """获取激活虚拟环境的命令"""
        if "conda" in venv_path.lower():
            env_name = os.path.basename(venv_path)
            print(env_name)
            env_name = "RNX"
            return f"conda activate {env_name}"
        else:
            # 普通 venv
            if sys.platform == "win32":
                activate_script = os.path.join(venv_path, "Scripts", "activate")
                return f"call {activate_script}"
            else:
                activate_script = os.path.join(venv_path, "bin", "activate")
                return f"source {activate_script}"

    def start_packaging(self):
        """开始打包"""
        # 获取用户输入
        project_path = self.entry_project.get()
        output_path = self.entry_output.get()
        app_name = self.entry_app_name.get()
        venv_index = self.cb_venv.current()

        if not all([project_path, output_path, app_name]):
            messagebox.showerror("错误", "请填写所有必填字段！")
            return

        # 构造 PyInstaller 命令
        cmd = [
            "pyinstaller",
            "--name", app_name,
            "--distpath", output_path,
            "--workpath", os.path.join(output_path, "build"),
        ]
        if self.var_onefile.get():
            cmd.append("--onefile")
        if not self.var_console.get():
            cmd.append("--noconsole")
        if self.var_upx.get():
            cmd.append("--upx-dir=upx")

        # 添加项目路径到搜索路径
        src_path = os.path.join(project_path, "src")
        cmd.extend(["--paths", src_path])

        # 主脚本路径
        main_script = os.path.join(src_path, "mian.py")
        cmd.append(main_script)

        # 如果有选择虚拟环境
        full_cmd = " ".join(cmd)
        if venv_index >= 0 and self.venv_paths:
            venv_name, venv_path = self.venv_paths[venv_index]
            activate_cmd = self.get_activate_command(venv_path)
            full_cmd = f"{activate_cmd} && {full_cmd}"
            self.log_output(f">>> 使用虚拟环境: {venv_name} ({venv_path})")

        self.log_output(f">>> 执行命令: {full_cmd}")

        # 执行打包
        try:
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                shell=True
            )
            for line in process.stdout:
                self.log_output(line.strip())
            
            if process.wait() == 0:
                self.log_output(">>> 打包成功！")
                messagebox.showinfo("完成", "打包成功！")
            else:
                self.log_output(">>> 打包失败！")
                messagebox.showerror("错误", "打包过程中出现错误！")
        except Exception as e:
            self.log_output(f">>> 错误: {str(e)}")
            messagebox.showerror("异常", f"发生异常:\n{str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    app = PackagerApp(root)
    root.mainloop()
