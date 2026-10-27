"""Developer UI smoke test; screenshot capture additionally requires Pillow and a display."""
import argparse
import tempfile
import tkinter as tk
from pathlib import Path
from projectpilot.service import Service
from projectpilot.ui import Application

def run(out=None):
    with tempfile.TemporaryDirectory() as d:
        root=tk.Tk();root.geometry('1280x820+20+20');s=Service(Path(d)/'workspace.db');app=Application(root,s);root.update()
        root.geometry('1280x820+20+20')
        def shot(name):
            root.update_idletasks();root.update()
            if out:
                from PIL import ImageGrab
                p=Path(out);p.mkdir(parents=True,exist_ok=True)
                x,y=root.winfo_rootx(),root.winfo_rooty();ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height()),xdisplay=root.winfo_screen()).save(p/(name+'.png'))
        shot('01-login')
        s.login('teacher','DemoPass123!');app.render();shot('02-overview')
        app.navigate('Projects');shot('03-projects')
        assert len(app.project_tree.get_children())==6
        app.search.insert(0,'finance');app.apply_filter();assert len(app.project_tree.get_children())==1
        app.query='';app.render()
        app.project_tree.selection_set('1');app.details();root.update()
        for w in root.winfo_children():
            if isinstance(w,tk.Toplevel):w.destroy()
        app.navigate('Students');shot('04-students');app.navigate('Activity');root.update();app.navigate('Settings');root.update()
        app.navigate('Overview');app.toggle_theme();shot('05-light-mode');app.toggle_theme()
        s.login('student','DemoPass123!');s.select(2);app.navigate('My selection');shot('06-student-selection')
        for page in ['Overview','Projects','Activity','Settings']:
            app.navigate(page);root.update()
        root.geometry('1040x720');app.navigate('Projects');root.update();assert app.project_tree.winfo_width()>300
        app.logout();root.update();root.destroy()
        print('PASS: login, all supervisor/student pages, search, project details, both themes, minimum window, logout')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out');run(p.parse_args().out)
