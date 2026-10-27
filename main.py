"""Launch with Python 3.10+; no pip dependencies required."""
import argparse
import os
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from projectpilot.advanced import Service
from projectpilot.advanced_ui import Application

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,default=(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'ProjectPilot'/'Python' if getattr(sys,'frozen',False) else Path(__file__).resolve().parent/'data'))
    args=parser.parse_args()
    root=tk.Tk()
    try:
        service=Service(args.data_dir/'workspace.db')
        Application(root,service)
    except Exception as exc:
        messagebox.showerror('Startup failed',str(exc));root.destroy();return
    root.mainloop()

if __name__=='__main__':main()
