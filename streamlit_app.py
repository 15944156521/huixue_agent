"""
Streamlit Cloud 入口文件
自动重定向到 app.py
"""
import subprocess
import sys

# 直接运行 app.py
if __name__ == "__main__":
    import runpy
    runpy.run_module('app', run_name='__main__')
