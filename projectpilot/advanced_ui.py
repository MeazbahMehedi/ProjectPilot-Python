"""3.0.1 desktop screens. No SQL is issued by the presentation layer."""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import date,timedelta
import shutil,webbrowser,threading,queue
from .ui import Application as CoreUI
from .config import APP_NAME,AUTHOR,GITHUB,ACCENT,EDITION
from .service import RuleError

class Application(CoreUI):
    def __init__(self,root,service):
        self.font_size=11;self.loaded=None;self.message='';self.persist_job=None;self.busy=False
        super().__init__(root,service)
        root.title(APP_NAME+' 3.0.1 | Academic workspace')
        root.geometry('1360x900');root.minsize(1100,720);root.protocol('WM_DELETE_WINDOW',self.close)
        root.bind('<Return>',lambda e:root.focus_get().invoke() if isinstance(root.focus_get(),tk.Button) else None)
        for n in range(1,10):root.bind(f'<Alt-Key-{n}>',lambda e,i=n:self.navigate(self.pages()[i-1]) if self.s.user and len(self.pages())>=i else None)
    def label(self,p,text,size=11,**kw):return super().label(p,text,max(9,round(size*self.font_size/11)),**kw)
    def button(self,p,text,cmd,primary=False):
        b=super().button(p,text,cmd,primary);b.configure(font=('Arial',max(9,self.font_size-1),'bold'),pady=9);return b
    def entry(self,p,secret=False,value=''):
        e=super().entry(p,secret,value);e.configure(font=('Arial',self.font_size));return e
    def colors(self):
        super().colors();ttk.Style().configure('Treeview',font=('Arial',self.font_size),rowheight=max(39,self.font_size*3));ttk.Style().configure('Treeview.Heading',font=('Arial',max(9,self.font_size-1),'bold'))
    def login_screen(self):
        self.loaded=None;super().login_screen()
        def visit(w):
            if isinstance(w,tk.Label) and 'teacher / DemoPass' in w.cget('text'):w.configure(text=self.s.bootstrap_admin+' / DemoPass123!\nteacher / DemoPass123!\nstudent / DemoPass123!')
            for child in w.winfo_children():visit(child)
        visit(self.root)
    def pages(self):
        role=self.s.user['role'];return ['Overview','Projects','Applications']+(['Teams'] if role=='student' else ['Students'])+['Progress','Submissions','Notifications']+(['Administration'] if role=='admin' else [])+(['Import & reports'] if role!='student' else ['Reports'])+['Activity','Settings']
    def save_state(self):
        if self.s.user:
            self.s.save_preferences(dark=self.dark,width=self.root.winfo_width(),height=self.root.winfo_height(),font_size=self.font_size,query=self.query,category=self.filter,favorites=self.only_favorites)
    def close(self):
        if self.busy:messagebox.showinfo(APP_NAME,'Please wait for the current import to finish.',parent=self.root);return
        try:self.save_state()
        except Exception:pass
        self.root.destroy()
    def logout(self):self.save_state();self.loaded=None;super().logout()
    def toggle_theme(self):self.dark=not self.dark;self.save_state();self.colors();self.render()
    def navigate(self,page):self.page=page;self.render()
    def notice(self,text):self.message=text
    def render(self):
        if not self.s.user:return self.login_screen()
        if self.loaded!=self.s.user['id']:
            p=self.s.preferences();self.loaded=self.s.user['id'];self.dark=p.get('dark',True);self.font_size=int(p.get('font_size',11));self.query=p.get('query','');self.filter=p.get('category','All categories');self.only_favorites=p.get('favorites',False)
            self.root.geometry(f"{max(1100,min(1600,int(p.get('width',1360))))}x{max(720,min(1000,int(p.get('height',900))))}")
        self.s.auth();self.clear();self.colors();role=self.s.user['role']
        side=tk.Frame(self.root,bg=self.panel,width=218);side.pack(side='left',fill='y');side.pack_propagate(False)
        self.label(side,APP_NAME,18,bold=True,color=ACCENT).pack(anchor='w',padx=20,pady=(26,5));self.label(side,'WORKSPACE / 3.0.1',9,color=self.muted,bold=True).pack(anchor='w',padx=20,pady=(0,20))
        ns=self.s.notifications();unread=sum(not n['is_read'] for n in ns)
        for page in self.pages():
            text=page+(f' ({unread})' if page=='Notifications' and unread else '')
            self.button(side,text,lambda p=page:self.navigate(p),page==self.page).pack(fill='x',padx=12,pady=3)
        self.button(side,'Sign out',self.logout).pack(side='bottom',fill='x',padx=15,pady=17)
        self.label(side,role.upper()+' / '+EDITION,9,color='#55cbb5',bold=True).pack(side='bottom',pady=6)
        outer=tk.Frame(self.root,bg=self.bg);outer.pack(side='left',fill='both',expand=True,padx=28,pady=24)
        header=tk.Frame(outer,bg=self.bg);header.pack(fill='x',pady=(0,18));self.label(header,'WORKSPACE / '+self.page.upper(),9,color=self.muted,bold=True).pack(anchor='w');self.label(header,self.page,27,bold=True).pack(side='left',pady=(8,0));self.button(header,'Light mode' if self.dark else 'Dark mode',self.toggle_theme).pack(side='right');self.label(header,self.s.user['name'],11,color=self.muted).pack(side='right',padx=15)
        self.content=tk.Frame(outer,bg=self.bg);self.content.pack(fill='both',expand=True)
        dispatch={'Overview':self.overview,'Projects':self.projects_page,'Students':self.students_page,'Applications':self.applications_page,'Teams':self.teams_page,'Progress':self.progress_page,'Submissions':self.submissions_page,'Notifications':self.notifications_page,'Administration':self.admin_page,'Import & reports':self.import_page,'Reports':self.import_page,'Activity':self.activity_page,'Settings':self.settings_page,'My selection':self.selection_page}
        dispatch.get(self.page,self.overview)()
        self.label(outer,self.message or '3.0.1 | Local workspace | Ctrl+F search | Alt+1-9 navigation | F5 refresh',9,color='#55cbb5' if self.message else self.muted).pack(anchor='w',pady=(14,0))
    def dialog(self,title,fields,on_save,choices=None):
        win=tk.Toplevel(self.root);win.title(title);win.configure(bg=self.panel);win.transient(self.root);win.grab_set();win.resizable(False,False)
        box=tk.Frame(win,bg=self.panel,padx=25,pady=20);box.pack(fill='both',expand=True);self.label(box,title,21,bold=True).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,12));controls={}
        for i,(key,label,value,secret) in enumerate(fields,1):
            self.label(box,label,10,color=self.muted).grid(row=i,column=0,sticky='nw',padx=(0,15),pady=9)
            if choices and key in choices:e=ttk.Combobox(box,values=choices[key],state='readonly',width=38);e.set(value)
            elif key in ('description','proposal','feedback','notes'):
                e=tk.Text(box,width=43,height=4,wrap='word',bg=self.soft,fg=self.text,insertbackground=self.text,bd=0,padx=8,pady=8,font=('Arial',self.font_size));e.insert('1.0',str(value))
                if title.startswith('Review application') and key=='proposal':e.configure(state='disabled')
            else:e=self.entry(box,secret,str(value));e.configure(width=42)
            e.grid(row=i,column=1,sticky='ew',ipady=6,pady=4);controls[key]=e
            if key=='attachment':
                def choose(e=e):
                    path=filedialog.askopenfilename(parent=win)
                    if path:e.delete(0,'end');e.insert(0,path)
                self.button(box,'Browse',choose).grid(row=i,column=2,padx=8)
        def values():return {k:e.get('1.0','end-1c') if isinstance(e,tk.Text) else e.get() for k,e in controls.items()}
        initial=values();error=self.label(box,'',10,color='#f6a38e',wraplength=530,justify='left');error.grid(row=len(fields)+1,column=0,columnspan=3,sticky='w',pady=6)
        def cancel():
            if values()!=initial and not messagebox.askyesno(APP_NAME,'Discard your unsaved changes?',parent=win):return
            win.destroy()
        def save():
            try:on_save(values())
            except Exception as exc:error.configure(text=str(exc));return
            self.notice('Saved successfully.');win.destroy()
            if self.s.user:self.render()
        buttons=tk.Frame(box,bg=self.panel);buttons.grid(row=len(fields)+2,column=0,columnspan=3,sticky='e',pady=12);self.button(buttons,'Cancel',cancel).pack(side='left',padx=8);self.button(buttons,'Save',save,True).pack(side='left');win.protocol('WM_DELETE_WINDOW',cancel);win.update_idletasks();win.geometry(f'+{self.root.winfo_rootx()+180}+{self.root.winfo_rooty()+70}');return win
    def overview(self):
        ps=self.s.projects();apps=self.s.applications();tasks=self.s.tasks();student=self.s.user['role']=='student'
        hero=self.card(self.content);hero.pack(fill='x',pady=(0,16));self.label(hero,'FROM IDEA TO FINAL PRESENTATION',10,color='#55cbb5',bold=True).pack(anchor='w');self.label(hero,'Your projects. A clearer path forward.',25,bold=True).pack(anchor='w',pady=(9,6));self.label(hero,'Discover, apply, collaborate and track every milestone in one place.',11,color=self.muted).pack(anchor='w');self.button(hero,'Explore project topics >',lambda:self.navigate('Projects'),True).pack(anchor='w',pady=(16,0))
        row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=(0,16));metrics=[('TOPICS',len(ps),ACCENT),('PENDING REQUESTS',sum(a['status'] in ('Pending','Changes requested') for a in apps),'#e9b76d'),('MILESTONES DONE',f"{sum(t['status']=='Done' for t in tasks)}/{len(tasks)}",'#55cbb5'),('UNREAD NOTICES',sum(not n['is_read'] for n in self.s.notifications()),'#f6a38e')]
        for i,(title,value,color) in enumerate(metrics):
            card=self.card(row);card.pack(side='left',expand=True,fill='both',padx=(0 if i==0 else 10,0));self.label(card,title,9,color=self.muted,bold=True).pack(anchor='w');self.label(card,str(value),25,color=color,bold=True).pack(anchor='w',pady=(10,0))
        lower=tk.Frame(self.content,bg=self.bg);lower.pack(fill='both',expand=True);left=self.card(lower);left.pack(side='left',fill='both',expand=True,padx=(0,14));self.label(left,'Next milestones',16,bold=True).pack(anchor='w',pady=(0,10))
        for t in [t for t in tasks if t['status']!='Done'][:5]:self.label(left,t['title']+' | '+t['student'],11).pack(anchor='w',pady=(10,3));self.label(left,'Due '+t['deadline']+' / '+t['status'],10,color=self.muted).pack(anchor='w')
        if not tasks:self.label(left,'Milestones appear when a project is assigned.',11,color=self.muted,wraplength=360,justify='left').pack(anchor='w',pady=15)
        if student:
            selection=self.s.selected();title=next((p['title'] for p in ps if p['id']==selection),'No project selected yet')
            self.label(left,'MY CURRENT PROJECT',9,color=ACCENT,bold=True).pack(anchor='w',pady=(25,8));self.label(left,title,12,wraplength=370,justify='left').pack(anchor='w');self.button(left,'Manage my selection',self.selection_window).pack(anchor='w',pady=14)
        right=self.card(lower);right.pack(side='left',fill='both',expand=True);self.label(right,'Recent updates',16,bold=True).pack(anchor='w',pady=(0,10))
        for n in self.s.notifications()[:4]:self.label(right,n['title'],11,bold=True).pack(anchor='w',pady=(10,3));self.label(right,n['message'],10,color=self.muted,wraplength=360,justify='left').pack(anchor='w')
        if not self.s.notifications():
            events=self.s.activity()[:4]
            for event in events:self.label(right,event['message'],11,wraplength=370,justify='left').pack(anchor='w',pady=(10,4));self.label(right,event['created'].replace('T',' '),9,color=self.muted).pack(anchor='w')
            if not events:self.label(right,'You are up to date. New events appear here.',11,color=self.muted,wraplength=360,justify='left').pack(anchor='w',pady=15)
    def selection_window(self):
        pid=self.s.selected()
        if pid:self.details(pid)
        else:self.navigate('Projects')
    def projects_page(self):
        self.subtitle('Search topics, compare selection modes, and check the deadline before applying.')
        tools=tk.Frame(self.content,bg=self.bg);tools.pack(fill='x',pady=(0,15));self.label(tools,'Search',10,color=self.muted).pack(side='left',padx=(0,8));self.search=self.entry(tools,value=self.query);self.search.pack(side='left',expand=True,fill='x',ipady=9,padx=(0,10));self.search.bind('<KeyRelease>',lambda e:self.apply_filter())
        cats=['All categories']+sorted({p['category'] for p in self.s.projects()});self.category=ttk.Combobox(tools,values=cats,state='readonly',width=22);self.category.set(self.filter if self.filter in cats else 'All categories');self.category.pack(side='left',padx=(0,10));self.category.bind('<<ComboboxSelected>>',lambda e:self.apply_filter());self.button(tools,'Saved',self.toggle_saved,self.only_favorites).pack(side='left')
        if self.s.user['role']!='student':self.button(tools,'+ New project',self.project_dialog,True).pack(side='left',padx=(10,0))
        columns=[('title','PROJECT'),('supervisor','SUPERVISOR'),('mode','MODE'),('seats','AVAILABLE'),('deadline','DEADLINE'),('days','DAYS LEFT'),('status','STATUS')];self.project_tree=self.table(self.content,columns,[],[275,135,95,80,110,90,80]);self.project_tree.bind('<Double-1>',lambda e:self.guard(self.details));self.counter=self.label(self.content,'',10,color=self.muted);self.counter.pack(anchor='w',pady=10)
        row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x');self.button(row,'Open project',self.details,True).pack(side='left');self.button(row,'Export CSV',lambda:self.export('csv')).pack(side='left',padx=10);self.button(row,'Export JSON',lambda:self.export('json')).pack(side='left')
        if self.s.user['role']=='student':self.button(row,'Cancel my selection',self.cancel_selection).pack(side='right')
        self.apply_filter()
    def apply_filter(self):
        self.query=self.search.get();self.filter=self.category.get();tree=self.project_tree;tree.delete(*tree.get_children())
        for p in self.s.projects():
            if self.query.casefold() not in ' '.join(str(p[k]) for k in ('title','supervisor','category','description')).casefold() or (self.filter!='All categories' and p['category']!=self.filter) or (self.only_favorites and not p['favorite']):continue
            days=(date.fromisoformat(p['deadline'])-date.today()).days;status='Expired' if p['status']=='Open' and days<0 else p['status'];tree.insert('','end',iid=str(p['id']),values=(('Saved | ' if p['favorite'] else '')+p['title'],p['supervisor'],p['selection_mode'],f"{p['available']}/{p['capacity']}",p['deadline'],str(days) if days>=0 else 'Passed',status))
        self.counter.configure(text=f'{len(tree.get_children())} topics | Seats show available / total | Direct = instant selection | Approval = proposal required')
        if self.persist_job:self.root.after_cancel(self.persist_job)
        self.persist_job=self.root.after(500,self.persist_filters)
    def persist_filters(self):
        self.persist_job=None
        if self.s.user:
            try:self.save_state()
            except Exception:pass
    def cancel_selection(self):
        if messagebox.askyesno(APP_NAME,'Cancel your current assignment? A Direct-mode waitlist may receive the seat.',parent=self.root):self.s.cancel();self.notice('Selection cancelled.');self.render()
    def project_dialog(self,p=None):
        p=p or dict(title='',supervisor=self.s.user['name'],category='Software Engineering',description='',capacity=3,deadline=(date.today()+timedelta(days=30)).isoformat(),status='Open',selection_mode='Approval',owner_id=self.s.user['id']);pid=p.get('id')
        fields=[(k,label,p[k],False) for k,label in [('title','Project title'),('supervisor','Supervisor display name'),('category','Category'),('description','Description'),('capacity','Total seats'),('deadline','Selection deadline'),('status','Status'),('selection_mode','Selection mode')]]
        if self.s.user['role']=='admin':fields.append(('owner_id','Supervisor account ID',p['owner_id'],False))
        self.dialog('Edit project' if pid else 'New project',fields,lambda d:self.s.save_project(d,pid),{'status':['Draft','Open','Closed'],'selection_mode':['Approval','Direct']})
    def details(self,pid=None):
        if pid is None:
            selected=self.project_tree.selection()
            if not selected:raise RuleError('Select a project first.')
            pid=int(selected[0])
        p=next((p for p in self.s.projects() if p['id']==pid),None)
        if not p:raise RuleError('Project no longer available.')
        win=tk.Toplevel(self.root);win.title(p['title']);win.configure(bg=self.panel);win.geometry('780x580');win.transient(self.root);win.grab_set();box=self.card(win);box.pack(fill='both',expand=True)
        self.label(box,p['category'].upper()+' / '+p['selection_mode'].upper(),10,color='#55cbb5',bold=True).pack(anchor='w');self.label(box,p['title'],23,bold=True,wraplength=710,justify='left').pack(anchor='w',pady=15);self.label(box,f"{p['supervisor']} | {p['status']} | Deadline {p['deadline']}",11,color=self.muted).pack(anchor='w');self.label(box,f"{p['available']} / {p['capacity']} seats available",16,color=ACCENT,bold=True).pack(anchor='w',pady=15)
        canvas=tk.Canvas(box,bg=self.soft,height=7,highlightthickness=0);canvas.pack(fill='x');canvas.bind('<Configure>',lambda e:canvas.create_rectangle(0,0,e.width*p['enrolled']/p['capacity'],7,fill=ACCENT,outline=''))
        desc=tk.Text(box,bg=self.soft,fg=self.text,wrap='word',height=7,font=('Arial',self.font_size),bd=0,padx=14,pady=14);desc.insert('1.0',p['description']);desc.configure(state='disabled');desc.pack(expand=True,fill='both',pady=18)
        self.label(box,'Supervisor review is required before seats are assigned.' if p['selection_mode']=='Approval' else 'Direct selection is immediate. Waitlists apply only when full.',10,color=self.muted).pack(anchor='w',pady=(0,15));row=tk.Frame(box,bg=self.panel);row.pack(fill='x')
        def done(fn):fn();win.destroy();self.notice('Updated successfully.');self.render()
        if self.s.user['role']!='student':self.button(row,'Edit',lambda:(win.destroy(),self.project_dialog(p)),True).pack(side='left');self.button(row,'Delete',lambda:done(lambda:self.s.delete_project(pid)) if messagebox.askyesno(APP_NAME,'Delete this project and its associated records?',parent=win) else None).pack(side='left',padx=8)
        elif p['selection_mode']=='Approval':
            def propose():
                win.destroy();self.dialog('Submit project application',[('proposal','Proposal / team plan','',False)],lambda d:self.s.apply(pid,d['proposal']))
            self.button(row,'Apply with proposal',propose,True).pack(side='left')
        else:self.button(row,'Select / switch',lambda:done(lambda:self.s.select(pid)),True).pack(side='left');self.button(row,'Leave waitlist' if p['waiting'] else 'Join waitlist',lambda:done(lambda:self.s.wait(pid))).pack(side='left',padx=8)
        self.button(row,'Unsave' if p['favorite'] else 'Save topic',lambda:done(lambda:self.s.favorite(pid))).pack(side='left',padx=8);self.button(row,'Close',win.destroy).pack(side='right')
    def select_row(self,tree,rows,key='id'):
        selected=tree.selection()
        if not selected:raise RuleError('Select a row first.')
        return next(r for r in rows if str(r[key])==selected[0])
    def applications_page(self):
        self.subtitle('Proposals, team applications, review decisions and requested changes.')
        rows=self.s.applications();tree=self.table(self.content,[('project','PROJECT'),('applicant','APPLICANT'),('team','TEAM'),('count','MEMBERS'),('status','STATUS')],[(r['id'],[r['title'],r['applicant'],r['team'],r['member_count'],r['status']]) for r in rows],[270,150,160,80,160])
        def open_app():
            a=self.select_row(tree,rows)
            if self.s.user['role']=='student':
                fields=[('proposal','Proposal',a['proposal'],False)]
                if a['status']=='Changes requested' and a['applicant_id']==self.s.user['id']:self.dialog('Revise application | '+a['feedback'],fields,lambda d:self.s.resubmit(a['id'],d['proposal']))
                else:messagebox.showinfo(APP_NAME,a['proposal']+'\n\nStatus: '+a['status']+'\nFeedback: '+(a['feedback'] or 'Awaiting review'),parent=self.root)
            else:self.dialog('Review application #'+str(a['id']),[('proposal','Student proposal',a['proposal'],False),('decision','Decision','Approved',False),('feedback','Supervisor feedback',a['feedback'],False)],lambda d:self.s.review_application(a['id'],d['decision'],d['feedback']),{'decision':['Approved','Changes requested','Rejected']})
        row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=15);self.button(row,'Open / review application',open_app,True).pack(side='left')
        if self.s.user['role']=='student':self.button(row,'Withdraw application',lambda:(self.s.withdraw(self.select_row(tree,rows)['id']),self.render())).pack(side='left',padx=10)
    def teams_page(self):
        t=self.s.team();self.subtitle('Invite classmates, agree member roles, and let the leader submit one team proposal.')
        if t:
            self.label(self.content,t['name']+' | Leader: '+t['leader_id'],18,bold=True).pack(anchor='w',pady=(0,12));members=t['members'];tree=self.table(self.content,[('id','ACCOUNT'),('name','MEMBER'),('role','ROLE')],[(r['id'],[r['id'],r['name'],r['role']]) for r in members],[140,230,200]);tree.configure(height=4)
            row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=12)
            if t['leader_id']==self.s.user['id']:
                self.button(row,'Invite student',lambda:self.dialog('Invite a classmate',[('id','Student account ID','',False)],lambda d:self.s.invite(d['id'])),True).pack(side='left')
                self.button(row,'Set member role',lambda:self.dialog('Member role',[('role','Role','Developer',False)],lambda d:self.s.team_role(self.select_row(tree,members)['id'],d['role']))).pack(side='left',padx=10)
            self.button(row,'Leave / dissolve team',lambda:(self.s.leave_team(),self.render())).pack(side='left')
        else:self.button(self.content,'Create team',lambda:self.dialog('Create your team',[('name','Team name','',False)],lambda d:self.s.create_team(d['name'])),True).pack(anchor='w',pady=15)
        self.label(self.content,'Incoming invitations',15,bold=True).pack(anchor='w',pady=(18,12));invites=self.s.invitations();it=self.table(self.content,[('team','TEAM'),('status','STATUS')],[(r['id'],[r['team'],r['status']]) for r in invites],[350,150]);it.configure(height=3);row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=12)
        for text,accept in [('Accept invitation',True),('Decline',False)]:self.button(row,text,lambda a=accept:(self.s.respond_invite(self.select_row(it,invites)['id'],a),self.render()),accept).pack(side='left',padx=(0,10))
    def progress_page(self):
        rows=self.s.tasks();done=sum(r['status']=='Done' for r in rows);self.subtitle(f'{done} of {len(rows)} milestones complete | '+(str(round(done/len(rows)*100)) if rows else '0')+'% overall progress')
        tree=self.table(self.content,[('student','STUDENT'),('project','PROJECT'),('title','MILESTONE'),('due','DEADLINE'),('status','STATUS')],[(r['id'],[r['student'],r['project'],r['title'],r['deadline'],r['status']]) for r in rows],[150,280,150,120,120]);row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=15)
        for status in ['In progress','Done','Todo']:self.button(row,status,lambda st=status:(self.s.update_task(self.select_row(tree,rows)['id'],st),self.render()),status=='Done').pack(side='left',padx=(0,10))
        if self.s.user['role']!='student':
            ps=self.s.projects();options=[f"{p['id']} | {p['title']}" for p in ps]
            self.button(row,'+ Add milestone',lambda:self.dialog('Add milestone for assigned students',[('project','Project',options[0] if options else '',False),('title','Milestone title','',False),('deadline','Deadline',(date.today()+timedelta(days=7)).isoformat(),False)],lambda d:self.s.add_task(int(d['project'].split(' | ')[0]),d['title'],d['deadline']),{'project':options})).pack(side='right')
    def submissions_page(self):
        self.subtitle('Share documents or code links, receive feedback, and submit a revised version when needed.');rows=self.s.submissions();tree=self.table(self.content,[('student','STUDENT'),('project','PROJECT'),('title','SUBMISSION'),('file','ATTACHMENT'),('status','STATUS')],[(r['id'],[r['student'],r['project'],r['title'],r['filename'] or 'Link only',r['status']]) for r in rows],[150,240,220,140,140]);row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=15)
        if self.s.user['role']=='student':self.button(row,'+ Submit work',lambda:self.dialog('Submit report or code',[('title','Submission title','',False),('link','Report / repository URL','',False),('attachment','Local document (optional)','',False),('notes','Notes','',False)],lambda d:self.s.submit(d['title'],d['link'],d['notes'],d['attachment'])),True).pack(side='left',padx=(0,10))
        else:self.button(row,'Review / feedback',lambda:self.dialog('Review submission',[('status','Decision','Accepted',False),('feedback','Feedback','',False)],lambda d:self.s.review_submission(self.select_row(tree,rows)['id'],d['status'],d['feedback']),{'status':['Accepted','Changes requested']}),True).pack(side='left',padx=(0,10))
        def details():
            r=self.select_row(tree,rows);messagebox.showinfo(APP_NAME,r['title']+'\n\n'+r['notes']+'\n\nLink: '+r['link']+'\n\nFeedback: '+(r['feedback'] or 'Awaiting review'),parent=self.root)
        self.button(row,'View details',details).pack(side='left',padx=(0,10))
        def save_file():
            r=self.select_row(tree,rows);source=self.s.attachment_path(r['id']);target=filedialog.asksaveasfilename(parent=self.root,initialfile=r['filename'])
            if target:shutil.copy2(source,target);self.notice('Attachment copy saved.');self.render()
        self.button(row,'Save attachment',save_file).pack(side='left',padx=(0,10))
        def open_link():
            r=self.select_row(tree,rows)
            if not r['link']:raise RuleError('This submission has no link.')
            webbrowser.open(r['link'])
        self.button(row,'Open link',open_link).pack(side='left')
    def notifications_page(self):
        self.subtitle('Account updates, invitations, approvals, feedback and approaching deadlines.');rows=self.s.notifications();self.table(self.content,[('read','STATE'),('title','NOTICE'),('message','DETAILS'),('created','WHEN')],[(r['id'],['Read' if r['is_read'] else 'NEW',r['title'],r['message'],r['created'].replace('T',' ')]) for r in rows],[80,190,500,170]);self.button(self.content,'Mark all as read',lambda:(self.s.read_notifications(),self.render()),True).pack(anchor='w',pady=15)
    def admin_page(self):
        rows=self.s.accounts();config=self.s.settings();self.subtitle(f"{len(rows)} accounts | Selection period: {'Open' if config.get('selection_enabled','1')=='1' else 'Closed'} | {config.get('selection_start') or 'Any start'} to {config.get('selection_end') or 'Any end'}")
        tree=self.table(self.content,[('id','ACCOUNT'),('name','NAME'),('major','DEPARTMENT / MAJOR'),('role','ROLE'),('active','STATE')],[(r['id'],[r['id'],r['name'],r['major'],r['role'],'Active' if r['active'] else 'Disabled']) for r in rows],[140,200,250,120,100]);row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=15)
        def account(edit=False):
            a=self.select_row(tree,rows) if edit else dict(id='',name='',major='',role='student',active=1)
            fields=[] if edit else [('id','Account ID','',False)]
            fields += [(k,label,a[k],False) for k,label in [('name','Name'),('major','Department / major'),('role','Role')]]+[('active','Account state','Active' if a['active'] else 'Disabled',False),('password','New password' if edit else 'Initial password','',True)]
            self.dialog('Manage account' if edit else 'Create account',fields,lambda d:self.s.manage_account(a['id'] if edit else d['id'],d['name'],d['major'],d['role'],d['password'],d['active']=='Active'),{'role':['student','teacher','admin'],'active':['Active','Disabled']})
        self.button(row,'+ Create account',account,True).pack(side='left');self.button(row,'Edit / reset password',lambda:account(True)).pack(side='left',padx=10)
        self.button(row,'Selection period',lambda:self.dialog('Configure selection period',[('start','Start date (optional)',config.get('selection_start',''),False),('end','End date (optional)',config.get('selection_end',''),False),('enabled','State','Open' if config.get('selection_enabled','1')=='1' else 'Closed',False)],lambda d:self.s.save_settings(d['start'],d['end'],'1' if d['enabled']=='Open' else '0'),{'enabled':['Open','Closed']})).pack(side='right')
    def import_page(self):
        self.subtitle('Preview imported rows before saving, or create a printable report from your permitted records.')
        reports=self.card(self.content);reports.pack(fill='x',pady=(0,18));self.label(reports,'PDF reports',19,bold=True).pack(anchor='w');self.label(reports,'Project summaries, assignments, progress and supervisor workload.',11,color=self.muted).pack(anchor='w',pady=10)
        def pdf():
            choices=['Project summary','Assignments','Progress']+(['Workload'] if self.s.user['role']!='student' else [])
            def create(d):
                from .reports import write_pdf
                path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.pdf',initialfile=APP_NAME+'-'+d['kind']+'.pdf')
                if path:self.s.validate_output(path);write_pdf(path,APP_NAME+' | '+d['kind'],self.s.report_lines(d['kind']),self.s.user['name'])
            self.dialog('Export PDF report',[('kind','Report','Project summary',False)],create,{'kind':choices})
        self.button(reports,'Create PDF report',pdf,True).pack(anchor='w')
        if self.s.user['role']=='student':return
        imports=self.card(self.content);imports.pack(fill='x');self.label(imports,'Validated CSV imports',19,bold=True).pack(anchor='w');self.label(imports,'Up to 2,000 rows. The preview hides passwords. Imports commit as a single transaction.',11,color=self.muted,wraplength=850,justify='left').pack(anchor='w',pady=12)
        row=tk.Frame(imports,bg=self.panel);row.pack(fill='x')
        def load(kind):
            def choose(d):
                path=filedialog.askopenfilename(parent=self.root,filetypes=[('CSV','*.csv')])
                if path:
                    preview=self.s.preview_import(path,kind,d.get('password',''));self.root.after_idle(lambda:self.preview_window(preview))
            if kind=='students':self.dialog('Student import credentials',[('password','Fallback initial password','',True)],choose)
            else:choose({})
        self.button(row,'Import projects',lambda:load('projects'),True).pack(side='left')
        if self.s.user['role']=='admin':
            self.button(row,'Import students',lambda:load('students')).pack(side='left',padx=10)
            def legacy():
                def choose(d):
                    p=filedialog.askopenfilename(parent=self.root,title='Choose legacy Projects CSV',filetypes=[('CSV','*.csv')]);s=filedialog.askopenfilename(parent=self.root,title='Choose legacy Students CSV',filetypes=[('CSV','*.csv')]) if p else ''
                    if p and s:
                        preview=self.s.preview_legacy(p,s,d['password'],d['deadline']);self.root.after_idle(lambda:self.preview_window(preview))
                self.dialog('Migrate original MySQL exports',[('password','Initial student password','',True),('deadline','Selection deadline',(date.today()+timedelta(days=30)).isoformat(),False)],choose)
            self.button(row,'Legacy paired migration',legacy).pack(side='left')
        self.label(imports,'CSV templates and legacy export instructions are in docs/import-templates/.',10,color=self.muted).pack(anchor='w',pady=(18,0))
    def preview_window(self,preview):
        win=tk.Toplevel(self.root);win.title('Import preview');win.configure(bg=self.bg);win.geometry('950x580');box=tk.Frame(win,bg=self.bg,padx=22,pady=22);box.pack(fill='both',expand=True);self.label(box,f"Review {len(preview['rows'])} rows before importing",20,bold=True).pack(anchor='w',pady=(0,15));self.table(box,[('id','ID / TITLE'),('details','PREVIEW (passwords hidden)')],[(i,[r.get('id',r.get('title','')), ' | '.join(str(v) for k,v in r.items() if k not in ('password','id','title'))]) for i,r in enumerate(preview['rows'])],[260,600])
        status=self.label(box,'',10,color=self.muted);status.pack(anchor='w',pady=8)
        progress=ttk.Progressbar(box,mode='indeterminate');progress.pack(fill='x')
        def finished(count=None,error=None):
            self.busy=False;progress.stop();button.configure(state='normal');win.protocol('WM_DELETE_WINDOW',win.destroy)
            if error:status.configure(text=str(error),fg='#f6a38e');return
            win.destroy();self.notice(f'Imported {count} records.');self.render()
        def commit():
            self.busy=True;button.configure(state='disabled');status.configure(text='Importing records. Please wait...');progress.start();win.grab_set();win.protocol('WM_DELETE_WINDOW',lambda:None)
            if self.persist_job:self.root.after_cancel(self.persist_job);self.persist_job=None
            results=queue.Queue()
            def worker():
                try:
                    count=self.s.commit_legacy(preview) if preview['kind']=='legacy' else self.s.commit_import(preview)
                    results.put((count,None))
                except Exception as exc:results.put((None,exc))
            def poll_result():
                try:count,error=results.get_nowait()
                except queue.Empty:self.root.after(40,poll_result);return
                finished(count,error)
            threading.Thread(target=worker,daemon=True).start();self.root.after(40,poll_result)
        button=self.button(box,'Confirm import',commit,True);button.pack(anchor='e',pady=(15,0))
    def settings_page(self):
        self.subtitle('Preferences save for your account and load when you sign in again.');card=self.card(self.content);card.pack(fill='x');self.label(card,APP_NAME+' 3.0.1 | '+EDITION,23,bold=True).pack(anchor='w');self.label(card,'Developer: '+AUTHOR if AUTHOR else 'Personal distribution',11,color=self.muted).pack(anchor='w',pady=12)
        if GITHUB:self.button(card,'Developer GitHub',lambda:webbrowser.open(GITHUB)).pack(anchor='w',pady=8)
        row=tk.Frame(self.content,bg=self.bg);row.pack(fill='x',pady=22)
        self.button(row,'Change password',lambda:self.dialog('Change password',[('old','Current password','',True),('new','New password','',True)],lambda d:self.s.change_password(d['old'],d['new'])),True).pack(side='left');self.button(row,'Toggle theme',self.toggle_theme).pack(side='left',padx=10)
        def size(d):self.font_size=int(d['size']);self.save_state()
        self.button(row,'Text size',lambda:self.dialog('Accessible text size',[('size','Font size',str(self.font_size),False)],size,{'size':['10','11','12','13','14']})).pack(side='left')
        if self.s.user['role']=='admin':
            def backup():
                path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.zip',initialfile=APP_NAME+'-backup.zip')
                if path:self.s.backup_bundle(path);self.notice('Workspace and attachment backup saved.');self.render()
            self.button(row,'Backup with attachments',backup).pack(side='left',padx=10)
        self.label(self.content,'Saved: theme, text size, window dimensions, search and category filters.\n\nKeyboard: Tab / Shift+Tab moves focus, Enter activates focused controls.\nCtrl+F searches projects. Alt+1-9 switches pages. F5 refreshes.\n\nAdmin password resets are local; no email or internet account is required.\nSee README.md for upgrading, restoring backups and Windows installer builds.',11,color=self.muted,justify='left').pack(anchor='w',pady=10)
