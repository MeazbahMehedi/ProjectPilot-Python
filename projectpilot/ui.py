"""Tkinter presentation layer. All data changes go through Service."""
import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, timedelta
from pathlib import Path
import webbrowser
from .config import APP_NAME, EDITION, AUTHOR, GITHUB, ACCENT
from .service import RuleError

class Application:
    def __init__(self, root, service):
        self.root=root;self.s=service;self.dark=True;self.page='Overview';self.query='';self.filter='All categories';self.only_favorites=False
        root.title(f'{APP_NAME} · Project selection workspace');root.geometry('1280x820');root.minsize(1040,720)
        root.option_add('*Font',('Arial',10))
        self.colors();self.login_screen()
        root.bind('<Control-f>',self.focus_search)
        root.bind('<F5>',lambda e:self.render() if self.s.user else None)

    def colors(self):
        self.bg='#10131e' if self.dark else '#f2f4fa';self.panel='#191e2d' if self.dark else '#ffffff'
        self.text='#edf0fa' if self.dark else '#17213a';self.muted='#9ba7bf' if self.dark else '#5d6b83'
        self.line='#2a3248' if self.dark else '#dce2ef';self.soft='#232a3e' if self.dark else '#eaf0fb'
        self.root.configure(bg=self.bg)
        style=ttk.Style();style.theme_use('clam')
        style.configure('Treeview',background=self.panel,foreground=self.text,fieldbackground=self.panel,bordercolor=self.line,lightcolor=self.line,darkcolor=self.line,rowheight=43,borderwidth=0,font=('Arial',10))
        style.configure('Treeview.Heading',background=self.soft,foreground=self.muted,font=('Arial',10,'bold'),relief='flat',padding=10)
        style.map('Treeview',background=[('selected',ACCENT)],foreground=[('selected','white')])
        style.configure('TCombobox',fieldbackground=self.soft,background=self.soft,foreground=self.text,arrowcolor=self.text,padding=7)
        style.map('TCombobox',fieldbackground=[('readonly',self.soft)],foreground=[('readonly',self.text)])
        style.configure('Vertical.TScrollbar',background=self.soft,troughcolor=self.panel,arrowcolor=self.muted,borderwidth=0)
        style.configure('Horizontal.TScrollbar',background=self.soft,troughcolor=self.panel,arrowcolor=self.muted,borderwidth=0)

    def clear(self):
        for w in self.root.winfo_children(): w.destroy()

    def label(self,p,text,size=11,color=None,bg=None,bold=False,**kw):
        return tk.Label(p,text=text,font=('Arial',size,'bold' if bold else 'normal'),bg=bg or p.cget('bg'),fg=color or self.text,**kw)

    def button(self,p,text,cmd,primary=False):
        b=tk.Button(p,text=text,command=lambda:self.guard(cmd),bg=ACCENT if primary else self.soft,fg='white' if primary else self.text,activebackground=ACCENT,activeforeground='white',bd=0,padx=15,pady=10,cursor='hand2',highlightthickness=0,font=('Arial',10,'bold'),relief='flat')
        return b

    def guard(self,fn):
        try: return fn()
        except (RuleError,ValueError) as e: messagebox.showwarning(APP_NAME,str(e),parent=self.root)
        except Exception as e: messagebox.showerror(APP_NAME,'The operation could not be completed.\n'+str(e),parent=self.root)

    def entry(self,p,secret=False,value=''):
        e=tk.Entry(p,bg=self.soft,fg=self.text,insertbackground=self.text,bd=0,highlightthickness=1,highlightbackground=self.line,highlightcolor=ACCENT,font=('Arial',11),show='*' if secret else '')
        e.insert(0,value);return e

    def login_screen(self):
        self.clear();self.root.configure(bg=self.bg)
        shell=tk.Frame(self.root,bg=self.bg);shell.pack(expand=True,fill='both',padx=65,pady=60)
        intro=tk.Frame(shell,bg=self.bg);intro.pack(side='left',expand=True,fill='both',padx=(0,55))
        self.label(intro,APP_NAME[0]+' /  '+APP_NAME,23,bold=True,color=ACCENT).pack(anchor='w',pady=(35,65))
        self.label(intro,'Good ideas deserve\na great team.',36,bold=True,justify='left').pack(anchor='w')
        self.label(intro,'Explore topics. Find your focus.\nBuild something that matters.',16,color=self.muted,justify='left').pack(anchor='w',pady=25)
        self.label(intro,'01   DISCOVER     02   SELECT     03   CREATE',10,color='#55cbb5',bold=True).pack(anchor='w',pady=30)
        self.label(intro,EDITION+' edition  /  Local desktop workspace',10,color=self.muted).pack(anchor='w',side='bottom')
        form=tk.Frame(shell,bg=self.panel,padx=35,pady=35);form.pack(side='right',fill='y',pady=30)
        self.label(form,'Welcome back',24,bold=True).pack(anchor='w',pady=(0,6))
        self.label(form,'Sign in to your academic workspace.',11,color=self.muted).pack(anchor='w',pady=(0,25))
        fields=[]
        for title,secret in [('Account ID',False),('Password',True)]:
            self.label(form,title,10,color=self.muted).pack(anchor='w',pady=(12,7))
            e=self.entry(form,secret);e.configure(width=30);e.pack(fill='x',ipady=10);fields.append(e)
        def go():
            self.s.login(fields[0].get(),fields[1].get());self.page='Overview';self.render()
        self.button(form,'Sign in  >',go,True).pack(fill='x',pady=(25,10))
        self.button(form,'Create student account',self.register_dialog).pack(fill='x')
        self.label(form,'Try the included demo workspace',11,bold=True).pack(anchor='w',pady=(28,7))
        self.label(form,'teacher / DemoPass123!\nstudent / DemoPass123!',10,color=self.muted,justify='left').pack(anchor='w')
        self.label(form,'Demo data is fictional. Change passwords\nbefore using this workspace for real records.',9,color=self.muted,justify='left').pack(anchor='w',pady=15)
        fields[0].focus_set();fields[1].bind('<Return>',lambda e:self.guard(go))

    def dialog(self,title,fields,on_save,choices=None):
        win=tk.Toplevel(self.root);win.title(title);win.configure(bg=self.panel);win.transient(self.root);win.grab_set();win.resizable(False,False)
        box=tk.Frame(win,bg=self.panel,padx=26,pady=22);box.pack(fill='both',expand=True)
        self.label(box,title,21,bold=True).grid(row=0,column=0,columnspan=2,sticky='w',pady=(0,16))
        controls={}
        for i,(key,title,value,secret) in enumerate(fields,1):
            self.label(box,title,10,color=self.muted).grid(row=i,column=0,sticky='w',padx=(0,18),pady=8)
            if choices and key in choices:
                e=ttk.Combobox(box,values=choices[key],state='readonly',width=35);e.set(value)
            elif key=='description':
                e=tk.Text(box,bg=self.soft,fg=self.text,insertbackground=self.text,width=40,height=5,wrap='word',font=('Arial',11),bd=0,padx=8,pady=8)
                e.insert('1.0',str(value))
            else:
                e=self.entry(box,secret,str(value));e.configure(width=40)
            e.grid(row=i,column=1,sticky='ew',ipady=7,pady=5);controls[key]=e
        def save():
            on_save({k:(e.get('1.0','end-1c') if isinstance(e,tk.Text) else e.get()) for k,e in controls.items()});win.destroy()
            if self.s.user:self.render()
        row=tk.Frame(box,bg=self.panel);row.grid(row=len(fields)+1,column=0,columnspan=2,sticky='e',pady=(18,0))
        self.button(row,'Cancel',win.destroy).pack(side='left',padx=6)
        self.button(row,'Save',save,True).pack(side='left')
        win.update_idletasks();win.geometry(f'+{self.root.winfo_rootx()+200}+{self.root.winfo_rooty()+80}')
        return win

    def register_dialog(self):
        def save(d):
            self.s.register(d['id'],d['name'],d['major'],d['password']);messagebox.showinfo(APP_NAME,'Account created. You can now sign in.',parent=self.root)
        self.dialog('Create your student account',[('id','Account ID','',False),('name','Full name','',False),('major','Major','Software Engineering',False),('password','Password (8+ characters)','',True)],save)

    def toggle_theme(self): self.dark=not self.dark;self.colors();self.render()
    def logout(self): self.s.user=None;self.query='';self.login_screen()
    def navigate(self,page):self.page=page;self.query='';self.filter='All categories';self.only_favorites=False;self.render()
    def focus_search(self,event=None):
        if self.s.user:
            if self.page!='Projects':self.navigate('Projects')
            self.search.focus_set()

    def render(self):
        if not self.s.user:return self.login_screen()
        self.clear();self.colors()
        side=tk.Frame(self.root,bg=self.panel,width=220);side.pack(side='left',fill='y');side.pack_propagate(False)
        self.label(side,APP_NAME,20,bold=True,color=ACCENT).pack(anchor='w',padx=22,pady=(34,8))
        self.label(side,'PROJECT WORKSPACE',9,color=self.muted,bold=True).pack(anchor='w',padx=24,pady=(0,35))
        for page in ['Overview','Projects','Students' if self.s.user['role']=='teacher' else 'My selection','Activity','Settings']:
            b=self.button(side,page,lambda p=page:self.navigate(p),self.page==page);b.pack(fill='x',padx=14,pady=5,ipady=3)
        self.button(side,'Sign out',self.logout).pack(side='bottom',fill='x',padx=18,pady=22)
        self.label(side,EDITION+'  /  v2.0.0',9,color=self.muted).pack(side='bottom',pady=8)
        self.label(side,'SUPERVISOR' if self.s.user['role']=='teacher' else 'STUDENT',9,color='#55cbb5',bold=True).pack(side='bottom',pady=8)
        outer=tk.Frame(self.root,bg=self.bg);outer.pack(side='left',fill='both',expand=True,padx=30,pady=25)
        header=tk.Frame(outer,bg=self.bg);header.pack(fill='x',pady=(0,22))
        self.label(header,'WORKSPACE  /  '+self.page.upper(),9,color=self.muted,bold=True).pack(anchor='w')
        self.label(header,self.page,27,bold=True).pack(side='left',pady=(7,0))
        self.button(header,'Light mode' if self.dark else 'Dark mode',self.toggle_theme).pack(side='right',padx=(12,0))
        self.label(header,self.s.user['name'],11,color=self.muted).pack(side='right')
        self.content=tk.Frame(outer,bg=self.bg);self.content.pack(fill='both',expand=True)
        {'Overview':self.overview,'Projects':self.projects_page,'Students':self.students_page,'My selection':self.selection_page,'Activity':self.activity_page,'Settings':self.settings_page}[self.page]()
        self.label(outer,'LOCAL WORKSPACE  |  Changes save automatically     |     '+date.today().strftime('%d %b %Y'),9,color=self.muted).pack(anchor='w',pady=(16,0))

    def card(self,parent):return tk.Frame(parent,bg=self.panel,padx=22,pady=20,highlightthickness=1,highlightbackground=self.line)
    def subtitle(self,text):self.label(self.content,text,11,color=self.muted).pack(anchor='w',pady=(0,18))

    def overview(self):
        ps=self.s.projects();students=self.s.students();assigned=sum(bool(s['project_id']) for s in students)
        hero=self.card(self.content);hero.pack(fill='x',pady=(0,18))
        self.label(hero,'YOUR NEXT CHAPTER STARTS HERE',9,color='#55cbb5',bold=True).pack(anchor='w')
        self.label(hero,'Turn curiosity into a project.',25,bold=True).pack(anchor='w',pady=(9,5))
        self.label(hero,'A clear view of your topics, teams, and next steps.',11,color=self.muted).pack(anchor='w')
        self.button(hero,'Explore the project catalog  >',lambda:self.navigate('Projects'),True).pack(anchor='w',pady=(17,0))
        row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=(0,18))
        metrics=[('PROJECT TOPICS',len(ps),ACCENT),('AVAILABLE SEATS',sum(p['available'] for p in ps if p['status']=='Open' and p['deadline']>=date.today().isoformat()),'#55cbb5'),('STUDENTS' if self.s.user['role']=='teacher' else 'MY ASSIGNMENT',len(students) if self.s.user['role']=='teacher' else ('Selected' if assigned else 'Not yet'),'#e9b76d')]
        for i,(label,value,color) in enumerate(metrics):
            card=self.card(row);card.pack(side='left',fill='both',expand=True,padx=(0 if i==0 else 10,0))
            self.label(card,label,9,color=self.muted,bold=True).pack(anchor='w');self.label(card,str(value),26,color=color,bold=True).pack(anchor='w',pady=(9,0))
        lower=tk.Frame(self.content,bg=self.bg);lower.pack(fill='both',expand=True)
        chart=self.card(lower);chart.pack(side='left',fill='both',expand=True,padx=(0,15))
        self.label(chart,'Seats by topic',15,bold=True).pack(anchor='w')
        self.label(chart,'Assigned / total capacity',10,color=self.muted).pack(anchor='w',pady=(4,10))
        for p in ps[:4]:
            line=tk.Frame(chart,bg=self.panel);line.pack(fill='x',pady=6)
            title=p['title'] if len(p['title'])<31 else p['title'][:28]+'...'
            self.label(line,title,10).pack(side='left');self.label(line,f"{p['enrolled']} / {p['capacity']}",10,color=self.muted).pack(side='right')
            canvas=tk.Canvas(chart,height=6,bg=self.soft,highlightthickness=0);canvas.pack(fill='x')
            canvas.bind('<Configure>',lambda e,p=p,c=canvas:(c.delete('all'),c.create_rectangle(0,0,e.width*p['enrolled']/p['capacity'],6,fill=ACCENT,outline='')))
        recent=self.card(lower);recent.pack(side='right',fill='both',expand=True)
        self.label(recent,'Recent activity',15,bold=True).pack(anchor='w',pady=(0,10))
        for r in self.s.activity()[:4]:
            self.label(recent,r['message'],10,wraplength=310,justify='left').pack(anchor='w',pady=(8,2))
            self.label(recent,r['created'].replace('T','  '),9,color=self.muted).pack(anchor='w')

    def table(self,parent,columns,rows,widths=None):
        frame=tk.Frame(parent,bg=self.panel);frame.pack(fill='both',expand=True)
        tree=ttk.Treeview(frame,columns=[k for k,t in columns],show='headings',selectmode='browse')
        sy=ttk.Scrollbar(frame,orient='vertical',command=tree.yview);sx=ttk.Scrollbar(frame,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=sy.set,xscrollcommand=sx.set)
        tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns');sx.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        for i,(key,title) in enumerate(columns):
            tree.heading(key,text=title,command=lambda k=key:self.sort_table(tree,k,False));tree.column(key,width=widths[i] if widths else 140,minwidth=80,stretch=True)
        for iid,values in rows:tree.insert('', 'end',iid=str(iid),values=values)
        return tree

    def sort_table(self,t,k,reverse):
        def key(i):
            x=t.set(i,k)
            try:return (0,float(x))
            except ValueError:return (1,x.casefold())
        for i,iid in enumerate(sorted(t.get_children(),key=key,reverse=reverse)): t.move(iid,'',i)
        t.heading(k,command=lambda:self.sort_table(t,k,not reverse))

    def projects_page(self):
        self.subtitle('Discover a topic, check availability, and find your next team.')
        tools=tk.Frame(self.content,bg=self.bg);tools.pack(fill='x',pady=(0,16))
        self.label(tools,'Search',10,color=self.muted).pack(side='left',padx=(0,8))
        self.search=self.entry(tools,value=self.query);self.search.pack(side='left',fill='x',expand=True,ipady=11,padx=(0,12))
        self.search.bind('<KeyRelease>',lambda e:self.apply_filter())
        self.category=ttk.Combobox(tools,values=['All categories']+sorted({p['category'] for p in self.s.projects()}),state='readonly',width=23);self.category.set(self.filter);self.category.pack(side='left',padx=(0,10));self.category.bind('<<ComboboxSelected>>',lambda e:self.apply_filter())
        self.button(tools,'+ Saved' if self.only_favorites else ' Saved',self.toggle_saved).pack(side='left')
        if self.s.user['role']=='teacher':self.button(tools,'+ New project',self.project_dialog,True).pack(side='left',padx=(10,0))
        self.project_tree=self.table(self.content,[('title','PROJECT TITLE'),('supervisor','SUPERVISOR'),('category','CATEGORY'),('seats','SEATS'),('deadline','DEADLINE'),('status','STATUS')],[],[250,120,170,80,110,90])
        self.project_tree.bind('<Double-1>',lambda e:self.guard(self.details))
        self.counter=self.label(self.content,'',10,color=self.muted);self.counter.pack(anchor='w',pady=10)
        actions=tk.Frame(self.content,bg=self.bg);actions.pack(fill='x')
        self.button(actions,'View details / actions',self.details,True).pack(side='left')
        self.button(actions,'Export CSV',lambda:self.export('csv')).pack(side='left',padx=10)
        self.button(actions,'Export JSON',lambda:self.export('json')).pack(side='left')
        self.apply_filter()

    def toggle_saved(self):self.only_favorites=not self.only_favorites;self.query=self.search.get();self.filter=self.category.get();self.render()
    def apply_filter(self):
        self.query=self.search.get();self.filter=self.category.get();tree=self.project_tree;tree.delete(*tree.get_children())
        for p in self.s.projects():
            if self.query.lower() not in (' '.join(str(p[k]) for k in ['title','supervisor','category','description'])).lower():continue
            if self.filter!='All categories' and p['category']!=self.filter:continue
            if self.only_favorites and not p['favorite']:continue
            status='Expired' if p['status']=='Open' and p['deadline']<date.today().isoformat() else p['status']
            tree.insert('','end',iid=str(p['id']),values=(('+ ' if p['favorite'] else '')+p['title'],p['supervisor'],p['category'],f"{p['available']}/{p['capacity']}",p['deadline'],status))
        self.counter.configure(text=f'{len(tree.get_children())} topics   |   Double-click a row for details   |   Ctrl+F to search')

    def details(self,pid=None):
        if pid is None:
            sel=self.project_tree.selection()
            if not sel:raise RuleError('Select a project row first.')
            pid=int(sel[0])
        p=next((p for p in self.s.projects() if p['id']==pid),None)
        if not p:raise RuleError('Project no longer exists.')
        win=tk.Toplevel(self.root);win.title(p['title']);win.configure(bg=self.panel);win.transient(self.root);win.grab_set();win.geometry('680x520');win.minsize(620,480)
        box=tk.Frame(win,bg=self.panel,padx=30,pady=25);box.pack(fill='both',expand=True)
        self.label(box,p['category'].upper(),10,color='#55cbb5',bold=True).pack(anchor='w')
        self.label(box,p['title'],23,bold=True,wraplength=610,justify='left').pack(anchor='w',pady=(10,18))
        self.label(box,f"{p['supervisor']}    |    {p['status']}    |    Due {p['deadline']}",11,color=self.muted).pack(anchor='w')
        self.label(box,f"{p['available']} seats available  /  {p['capacity']} total capacity",13,color=ACCENT,bold=True).pack(anchor='w',pady=18)
        text=tk.Text(box,bg=self.soft,fg=self.text,wrap='word',height=6,bd=0,padx=14,pady=14,font=('Arial',11));text.insert('1.0',p['description']);text.configure(state='disabled');text.pack(fill='both',expand=True)
        row=tk.Frame(box,bg=self.panel);row.pack(fill='x',pady=(18,0))
        def done(fn):fn();win.destroy();self.render()
        if self.s.user['role']=='teacher':
            self.button(row,'Edit project',lambda:(win.destroy(),self.project_dialog(p)),True).pack(side='left')
            def delete():
                if messagebox.askyesno(APP_NAME,'Delete this project and release assigned students?',parent=win):done(lambda:self.s.delete_project(pid))
            self.button(row,'Delete',delete).pack(side='left',padx=8)
        else:
            self.button(row,'Select / switch',lambda:done(lambda:self.s.select(pid)),True).pack(side='left')
            self.button(row,'Leave waitlist' if p['waiting'] else 'Join waitlist',lambda:done(lambda:self.s.wait(pid))).pack(side='left',padx=8)
        self.button(row,'Unsave' if p['favorite'] else 'Save topic',lambda:done(lambda:self.s.favorite(pid))).pack(side='left')
        self.button(row,'Close',win.destroy).pack(side='right')

    def project_dialog(self,p=None):
        data=p or dict(title='',supervisor=self.s.user['name'],category='Software Engineering',description='',capacity=3,deadline=(date.today()+timedelta(days=30)).isoformat(),status='Open')
        keys=[('title','Project title'),('supervisor','Supervisor'),('category','Category'),('description','Description'),('capacity','Total seats'),('deadline','Deadline (YYYY-MM-DD)'),('status','Status')]
        self.dialog('Edit project' if p else 'Create a new project',[(k,title,data[k],False) for k,title in keys],lambda d:self.s.save_project(d,p['id'] if p else None),{'status':['Draft','Open','Closed']})

    def students_page(self):
        self.subtitle('A live view of students and their current assignments.')
        rows=self.s.students()
        self.table(self.content,[('id','ACCOUNT ID'),('name','STUDENT'),('major','MAJOR'),('project','ASSIGNED PROJECT')],[(r['id'],[r[k] for k in ['id','name','major','project']]) for r in rows],[110,170,200,300])
        self.label(self.content,f"{len(rows)} students  |  {sum(bool(r['project_id']) for r in rows)} assigned",11,color=self.muted).pack(anchor='w',pady=15)
        self.button(self.content,'Export workspace JSON',lambda:self.export('json'),True).pack(anchor='w')

    def selection_page(self):
        pid=self.s.selected()
        if pid:
            p=next(p for p in self.s.projects() if p['id']==pid)
            card=self.card(self.content);card.pack(fill='x')
            self.label(card,'YOUR CURRENT PROJECT',10,color='#55cbb5',bold=True).pack(anchor='w')
            self.label(card,p['title'],25,bold=True).pack(anchor='w',pady=15)
            self.label(card,p['supervisor']+'   /   '+p['category'],12,color=self.muted).pack(anchor='w')
            self.label(card,p['description'],12,wraplength=750,justify='left').pack(anchor='w',pady=20)
            self.button(card,'View project details',lambda:self.details(pid),True).pack(anchor='w')
            def cancel():
                if messagebox.askyesno(APP_NAME,'Cancel your selection? A waiting student may receive this seat.',parent=self.root):self.s.cancel();self.render()
            self.button(card,'Cancel selection',cancel).pack(anchor='w',pady=12)
        else:
            self.subtitle('Your next project is waiting. Explore the catalog and select an open topic.')
            self.button(self.content,'Explore projects',lambda:self.navigate('Projects'),True).pack(anchor='w')
        waiting=[p['title'] for p in self.s.projects() if p['waiting']]
        self.label(self.content,'WAITLISTS',11,bold=True,color=ACCENT).pack(anchor='w',pady=(28,12))
        self.label(self.content,'\n'.join(waiting) if waiting else 'You are not on a waitlist.',12,color=self.muted,justify='left').pack(anchor='w')

    def activity_page(self):
        self.subtitle('Changes, selections, and waitlist promotions in one timeline.')
        rows=self.s.activity()
        self.table(self.content,[('time','WHEN'),('actor','ACCOUNT'),('message','ACTIVITY')],[(i,[r['created'].replace('T',' '),r['actor'],r['message']]) for i,r in enumerate(rows)],[180,120,530])

    def export(self,kind):
        path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.'+kind,filetypes=[(kind.upper(),'*.'+kind)],initialfile=APP_NAME+'-export.'+kind)
        if path:self.s.export(path,kind);messagebox.showinfo(APP_NAME,'Export saved.',parent=self.root)

    def settings_page(self):
        self.subtitle('Personalize your workspace and keep your data safe.')
        card=self.card(self.content);card.pack(fill='x')
        self.label(card,APP_NAME+' 2.0.0',23,bold=True).pack(anchor='w')
        self.label(card,EDITION+' edition | Student project selection and supervision',12,color=self.muted).pack(anchor='w',pady=12)
        self.label(card,'Developer: '+AUTHOR if AUTHOR else 'Personal edition',11).pack(anchor='w')
        if GITHUB:self.button(card,'Open developer GitHub',lambda:webbrowser.open(GITHUB)).pack(anchor='w',pady=15)
        row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=25)
        def password():
            self.dialog('Change password',[('old','Current password','',True),('new','New password','',True)],lambda d:self.s.change_password(d['old'],d['new']))
        self.button(row,'Change password',password,True).pack(side='left')
        self.button(row,'Toggle theme',self.toggle_theme).pack(side='left',padx=12)
        self.button(row,'Export JSON',lambda:self.export('json')).pack(side='left')
        if self.s.user['role']=='teacher':
            def backup():
                path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.db',initialfile=APP_NAME+'-backup.db')
                if path:self.s.backup(path);messagebox.showinfo(APP_NAME,'Backup saved.',parent=self.root)
            self.button(row,'Back up database',backup).pack(side='left',padx=12)
        self.label(self.content,'Keyboard shortcuts: Ctrl+F searches projects. F5 refreshes your view.\n\nData stays on this computer. Exports never include password hashes.\nFor restore instructions and the original Java > Python history, see README.md.',11,color=self.muted,justify='left').pack(anchor='w',pady=15)
