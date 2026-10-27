"""GUI workflow checks and reproducible screenshots; Pillow is optional for capture."""
import argparse,tempfile,tkinter as tk
from pathlib import Path
from projectpilot.advanced import Service
from projectpilot.advanced_ui import Application
from projectpilot.reports import write_pdf
from .demo_fixture import populate

def run(out=None):
    with tempfile.TemporaryDirectory() as d:
        folder=Path(d);s=Service(folder/'workspace.db');pid=populate(s,folder);root=tk.Tk();app=Application(root,s);root.geometry('1360x900+20+20');root.update()
        def shot(name):
            root.update_idletasks();root.update()
            if out:
                from PIL import ImageGrab
                target=Path(out);target.mkdir(parents=True,exist_ok=True);x,y=root.winfo_rootx(),root.winfo_rooty();ImageGrab.grab(bbox=(x,y,x+root.winfo_width(),y+root.winfo_height()),xdisplay=root.winfo_screen()).save(target/(name+'.png'))
        shot('01-login')
        def show(uid,page,name):s.login(uid,'DemoPass123!');app.page=page;app.render();shot(name)
        show('admin','Overview','02-overview');show('teacher','Projects','03-projects');assert len(app.project_tree.get_children())==7
        app.search.insert(0,'finance');app.apply_filter();assert len(app.project_tree.get_children())==1;app.search.delete(0,'end');app.apply_filter()
        app.project_tree.selection_set(str(pid));app.details();root.update()
        for w in root.winfo_children():
            if isinstance(w,tk.Toplevel):w.destroy()
        show('teacher','Applications','04-applications');show('student','Teams','05-teams');show('student3','Progress','06-progress');show('teacher','Submissions','07-submissions');show('student3','Notifications','08-notifications');show('admin','Administration','09-administration');show('admin','Import & reports','10-import-and-reports');app.navigate('Overview');app.toggle_theme();shot('11-light-mode');app.toggle_theme();app.navigate('Settings');shot('12-settings');show('student3','Overview','13-student-overview');show('teacher','Students','14-students')
        for uid in ['admin','teacher','student']:
            s.login(uid,'DemoPass123!');app.page='Overview';app.render()
            for page in app.pages():app.navigate(page);root.update()
        # Inline validation must leave the dialog open; cancel clean dialog must close.
        win=app.dialog('Validation check',[('title','Title','',False)],lambda v:(_ for _ in ()).throw(ValueError('Required title')))
        def buttons(w):
            result=[]
            for c in w.winfo_children():
                if isinstance(c,tk.Button):result.append(c)
                result+=buttons(c)
            return result
        next(b for b in buttons(win) if b.cget('text')=='Save').invoke();root.update();assert win.winfo_exists();next(b for b in buttons(win) if b.cget('text')=='Cancel').invoke()
        # Exercise the student-import form through the actual file-picker callback.
        from unittest.mock import patch
        s.login('admin','DemoPass123!');app.page='Import & reports';app.render();root.update()
        csvpath=folder/'ui-import.csv';csvpath.write_text('id,name,major\nui001,UI Demo,CS\n')
        with patch('projectpilot.advanced_ui.filedialog.askopenfilename',return_value=str(csvpath)):
            next(b for b in buttons(root) if b.cget('text')=='Import students').invoke();root.update()
            form=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
            def entries(w):
                found=[]
                for child in w.winfo_children():
                    if isinstance(child,tk.Entry):found.append(child)
                    found+=entries(child)
                return found
            entries(form)[0].insert(0,'LongPass123!');next(b for b in buttons(form) if b.cget('text')=='Save').invoke();root.update()
        preview=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel) and w.title()=='Import preview');assert preview.winfo_exists()
        next(b for b in buttons(preview) if b.cget('text')=='Confirm import').invoke()
        timed_out=[False]
        def poll():
            if not app.busy:root.quit()
            else:root.after(30,poll)
        def timeout():timed_out[0]=True;root.quit()
        root.after(30,poll);timeout_job=root.after(10000,timeout);root.mainloop();root.after_cancel(timeout_job);assert not timed_out[0];assert any(a['id']=='ui001' for a in s.accounts())
        root.geometry('1100x720');app.navigate('Projects');root.update();assert app.project_tree.winfo_width()>300;app.save_state();app.logout();root.update();root.destroy()
        if out:
            s.login('admin','DemoPass123!');write_pdf(Path(out).parent/'sample-report.pdf','ProjectPilot | Progress',s.report_lines('Progress'),s.user['name'])
        print('PASS 3.0.1 GUI: all role pages, topic search, details, inline validation, cancel, async CSV import, themes, preferences and compact layout')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out');run(p.parse_args().out)
