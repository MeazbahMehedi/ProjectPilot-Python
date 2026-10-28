"""Version 3.0.1 workflows, migrations and access control."""
from .service import Service as CoreService, RuleError, required, valid_password, password_hash
from datetime import date, timedelta
from pathlib import Path
import csv, json, secrets, shutil, sqlite3, tempfile, zipfile
from urllib.parse import urlparse

ACTIVE_APPLICATIONS=('Pending','Changes requested')
STAGES=('Proposal','Development','Testing','Report','Presentation')

class Service(CoreService):
    def __init__(self,path):
        existed=Path(path).exists()
        super().__init__(path)
        with self.connect() as source:
            old_schema='owner_id' not in {r[1] for r in source.execute('PRAGMA table_info(projects)')}
            backup=self.path.with_name('workspace.pre-3.0.1.db')
            if existed and old_schema and not backup.exists():
                with sqlite3.connect(backup) as dest:source.backup(dest)
        with self.connect() as c:
            cols={r[1] for r in c.execute('PRAGMA table_info(users)')}
            if 'active' not in cols:c.execute('ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1')
            cols={r[1] for r in c.execute('PRAGMA table_info(projects)')}
            if 'owner_id' not in cols:c.execute("ALTER TABLE projects ADD COLUMN owner_id TEXT NOT NULL DEFAULT 'teacher'")
            if 'selection_mode' not in cols:c.execute("ALTER TABLE projects ADD COLUMN selection_mode TEXT NOT NULL DEFAULT 'Direct'")
            c.executescript('''
            CREATE TABLE IF NOT EXISTS admins(user_id TEXT PRIMARY KEY REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS preferences(user_id TEXT PRIMARY KEY REFERENCES users(id),payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS teams(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,leader_id TEXT NOT NULL REFERENCES users(id));
            CREATE TABLE IF NOT EXISTS members(team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,user_id TEXT PRIMARY KEY REFERENCES users(id),role TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS invitations(id INTEGER PRIMARY KEY AUTOINCREMENT,team_id INTEGER REFERENCES teams(id) ON DELETE CASCADE,invitee TEXT REFERENCES users(id),status TEXT NOT NULL,UNIQUE(team_id,invitee));
            CREATE TABLE IF NOT EXISTS applications(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,applicant_id TEXT REFERENCES users(id),team_id INTEGER REFERENCES teams(id) ON DELETE SET NULL,proposal TEXT NOT NULL,status TEXT NOT NULL,feedback TEXT NOT NULL DEFAULT '',created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS application_members(application_id INTEGER REFERENCES applications(id) ON DELETE CASCADE,user_id TEXT REFERENCES users(id),PRIMARY KEY(application_id,user_id));
            CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT REFERENCES users(id),project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,title TEXT NOT NULL,deadline TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Todo');
            CREATE TABLE IF NOT EXISTS submissions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT REFERENCES users(id),project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,title TEXT NOT NULL,link TEXT NOT NULL,attachment TEXT NOT NULL,filename TEXT NOT NULL,notes TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'Submitted',feedback TEXT NOT NULL DEFAULT '',created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT REFERENCES users(id),title TEXT NOT NULL,message TEXT NOT NULL,is_read INTEGER NOT NULL DEFAULT 0,created TEXT NOT NULL,dedupe TEXT UNIQUE);
            ''')
            if 'team_name' not in {r[1] for r in c.execute('PRAGMA table_info(applications)')}:c.execute("ALTER TABLE applications ADD COLUMN team_name TEXT NOT NULL DEFAULT ''")
            if not c.execute("SELECT 1 FROM settings WHERE key='schema'").fetchone():
                # Reserve a unique bootstrap ID without overwriting a migrated user's account.
                uid='admin'
                while c.execute('SELECT 1 FROM users WHERE id=?',(uid,)).fetchone():uid='admin-'+secrets.token_hex(2)
                c.execute('INSERT INTO users(id,name,major,role,password,active) VALUES (?,?,?,?,?,1)',(uid,'Workspace Administrator','Administration','teacher',password_hash('DemoPass123!')))
                c.execute('INSERT INTO admins VALUES (?)',(uid,));c.execute("INSERT INTO settings VALUES ('bootstrap_admin',?)",(uid,))
                c.execute("INSERT INTO settings VALUES ('schema','3.0.1')")
                c.execute("INSERT INTO settings VALUES ('selection_enabled','1')")
                for r in c.execute('SELECT user_id,project_id FROM enrollments').fetchall():self._tasks(c,r[0],r[1])

    @property
    def bootstrap_admin(self):
        with self.connect() as c:return c.execute("SELECT value FROM settings WHERE key='bootstrap_admin'").fetchone()[0]

    def auth(self,teacher=False,admin=False):
        if not self.user:raise RuleError('Sign in first.')
        with self.connect() as c:r=c.execute('SELECT u.active,u.role,EXISTS(SELECT 1 FROM admins a WHERE a.user_id=u.id) is_admin FROM users u WHERE id=?',(self.user['id'],)).fetchone()
        if not r or not r[0]:raise RuleError('This account has been disabled. Contact the administrator.')
        self.user['role']='admin' if r['is_admin'] else r['role']
        if admin and self.user['role']!='admin':raise RuleError('Administrator access required.')
        if teacher and self.user['role'] not in ('teacher','admin'):raise RuleError('Supervisor access required.')
        return self.user['id']

    def login(self,uid,password):
        user=super().login(uid,password)
        with self.connect() as c:
            if c.execute('SELECT 1 FROM admins WHERE user_id=?',(user['id'],)).fetchone():user['role']='admin'
        try:self.auth()
        except Exception:self.user=None;raise
        return user

    def _owner(self,c,pid):
        self.auth(True);p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not p:raise RuleError('Project no longer exists.')
        if self.user['role']!='admin' and p['owner_id']!=self.user['id']:raise RuleError('You can manage only your own projects.')
        return p

    def projects(self):
        uid=self.auth()
        with self.connect() as c:
            rows=[dict(r) for r in c.execute('''SELECT p.*,COUNT(e.user_id) enrolled,p.capacity-COUNT(e.user_id) available,
            EXISTS(SELECT 1 FROM favorites f WHERE f.user_id=? AND f.project_id=p.id) favorite,
            EXISTS(SELECT 1 FROM waitlist w WHERE w.user_id=? AND w.project_id=p.id) waiting
            FROM projects p LEFT JOIN enrollments e ON e.project_id=p.id
            WHERE (?='admin' OR (?='teacher' AND p.owner_id=?) OR (?='student' AND p.status!='Draft')) GROUP BY p.id ORDER BY p.id''',(uid,uid,self.user['role'],self.user['role'],uid,self.user['role']))]
        return rows

    def students(self):
        uid=self.auth();role=self.user['role']
        with self.connect() as c:
            return [dict(r) for r in c.execute('''SELECT u.id,u.name,u.major,e.project_id,COALESCE(p.title,'Unassigned') project
            FROM users u LEFT JOIN enrollments e ON e.user_id=u.id LEFT JOIN projects p ON p.id=e.project_id WHERE u.role='student'
            AND (?='admin' OR (?='student' AND u.id=?) OR (?='teacher' AND (p.owner_id=? OR EXISTS(SELECT 1 FROM applications a JOIN application_members am ON am.application_id=a.id JOIN projects ap ON ap.id=a.project_id WHERE am.user_id=u.id AND ap.owner_id=?)))) ORDER BY u.name''',(role,role,uid,role,uid,uid))]

    def activity(self):
        uid=self.auth()
        with self.connect() as c:return [dict(r) for r in c.execute("SELECT actor,message,created FROM activity WHERE ?='admin' OR actor=? ORDER BY id DESC LIMIT 150",(self.user['role'],uid))]

    def settings(self):
        self.auth()
        with self.connect() as c:return dict(c.execute('SELECT key,value FROM settings'))

    def _window(self,c):
        config=dict(c.execute('SELECT key,value FROM settings'));today=date.today().isoformat()
        if config.get('selection_enabled','1')!='1' or (config.get('selection_start') and today<config['selection_start']) or (config.get('selection_end') and today>config['selection_end']):raise RuleError('The project selection period is closed.')

    def save_settings(self,start='',end='',enabled='1'):
        uid=self.auth(admin=True)
        try:
            start=date.fromisoformat(start).isoformat() if start else '';end=date.fromisoformat(end).isoformat() if end else ''
        except ValueError:raise RuleError('Use dates in YYYY-MM-DD format.') from None
        if start and end and start>end:raise RuleError('The start date must not be after the end date.')
        with self.transaction() as c:
            for k,v in [('selection_start',start),('selection_end',end),('selection_enabled',str(enabled))]:c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)',(k,v))
            if str(enabled)=='1':
                for p in c.execute('SELECT id FROM projects').fetchall():self.promote(c,p[0])
            self.log(c,uid,'Updated selection period')

    def preferences(self):
        uid=self.auth()
        with self.connect() as c:r=c.execute('SELECT payload FROM preferences WHERE user_id=?',(uid,)).fetchone()
        return json.loads(r[0]) if r else {}

    def save_preferences(self,**values):
        uid=self.auth();p=self.preferences();p.update({k:v for k,v in values.items() if k in ('dark','width','height','query','category','favorites','font_size')})
        if not 9<=int(p.get('font_size',11))<=16:raise RuleError('Text size must be 9–16.')
        with self.transaction() as c:c.execute('INSERT OR REPLACE INTO preferences VALUES (?,?)',(uid,json.dumps(p)))

    def accounts(self):
        self.auth(admin=True)
        with self.connect() as c:return [dict(r) for r in c.execute("SELECT id,name,major,CASE WHEN a.user_id IS NOT NULL THEN 'admin' ELSE role END role,active FROM users u LEFT JOIN admins a ON a.user_id=u.id ORDER BY role,id")]

    def manage_account(self,uid,name,major,role,password='',active=True):
        actor=self.auth(admin=True);uid=required(uid,'Account ID',40);name=required(name,'Name');major=required(major,'Department / major')
        if role not in ('admin','teacher','student'):raise RuleError('Invalid role.')
        if not all(x.isalnum() or x in '._-' for x in uid):raise RuleError('Invalid account ID.')
        if password:valid_password(password)
        with self.transaction() as c:
            old=c.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if old:
                uid=old['id'];was_admin=bool(c.execute('SELECT 1 FROM admins WHERE user_id=?',(uid,)).fetchone())
                if uid==actor and (not active or role!='admin'):raise RuleError('You cannot disable or demote your current administrator account.')
                if role=='student' and c.execute('SELECT 1 FROM projects WHERE owner_id=?',(uid,)).fetchone():raise RuleError('Transfer this supervisor\'s projects before changing the role.')
                if old['role']=='student' and role!='student' and (c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(uid,)).fetchone() or self._pending(c,uid)):raise RuleError('Resolve this student\'s assignment and applications first.')
                c.execute('UPDATE users SET name=?,major=?,role=?,active=? WHERE id=?',(name,major,'teacher' if role=='admin' else role,int(active),uid))
                if password:c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(password),uid))
            else:
                if not password:raise RuleError('A password is required for new accounts.')
                c.execute('INSERT INTO users(id,name,major,role,password,active) VALUES (?,?,?,?,?,?)',(uid,name,major,'teacher' if role=='admin' else role,password_hash(password),int(active)))
            c.execute('DELETE FROM admins WHERE user_id=?',(uid,))
            if role=='admin':c.execute('INSERT INTO admins VALUES (?)',(uid,))
            self.notify(c,uid,'Account updated','Your account settings or password were changed by an administrator.')
            self.log(c,actor,'Updated account: '+uid)

    def save_project(self,p,pid=None):
        uid=self.auth(True);p=dict(p)
        with self.transaction() as c:
            if pid:self._owner(c,pid)
            owner=p.get('owner_id',uid)
            if self.user['role']!='admin':owner=uid
            owner_row=c.execute("SELECT * FROM users WHERE id=? AND role='teacher' AND active=1",(owner,)).fetchone()
            if not owner_row:raise RuleError('Choose an active supervisor account as owner.')
            fields={k:required(p.get(k,''),k.title(),3000 if k=='description' else 120) for k in ('title','supervisor','category','description')}
            try:fields['capacity']=int(p['capacity']);fields['deadline']=date.fromisoformat(p['deadline']).isoformat()
            except (ValueError,TypeError,KeyError):raise RuleError('Enter a whole-number capacity and a YYYY-MM-DD deadline.') from None
            if not 1<=fields['capacity']<=10000:raise RuleError('Capacity must be 1–10,000.')
            fields.update(status=p.get('status','Open'),selection_mode=p.get('selection_mode','Approval'),owner_id=owner_row['id'])
            if fields['status'] not in ('Draft','Open','Closed') or fields['selection_mode'] not in ('Direct','Approval'):raise RuleError('Invalid status or selection mode.')
            if pid:
                count=c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]
                if fields['capacity']<count or (count and fields['status']=='Draft'):raise RuleError('Keep capacity at least the assigned count; assigned projects cannot be Draft.')
                old=c.execute('SELECT selection_mode FROM projects WHERE id=?',(pid,)).fetchone()[0]
                if old!=fields['selection_mode'] and c.execute("SELECT 1 FROM applications WHERE project_id=? AND status IN ('Pending','Changes requested')",(pid,)).fetchone():raise RuleError('Resolve pending applications before changing the selection mode.')
                if old!=fields['selection_mode']:c.execute('DELETE FROM waitlist WHERE project_id=?',(pid,))
                c.execute('UPDATE projects SET '+','.join(k+'=:'+k for k in fields)+' WHERE id=:id',dict(fields,id=pid))
            else:pid=c.execute('INSERT INTO projects('+','.join(fields)+') VALUES ('+','.join(':'+k for k in fields)+')',fields).lastrowid
            self.promote(c,pid);self.log(c,uid,'Saved project: '+fields['title'])
        return pid

    def delete_project(self,pid):
        with self.connect() as c:self._owner(c,pid)
        return super().delete_project(pid)

    def _open(self,c,pid):self._window(c);return super()._open(c,pid)
    def _pending(self,c,uid):return c.execute("SELECT 1 FROM application_members m JOIN applications a ON a.id=m.application_id WHERE m.user_id=? AND a.status IN ('Pending','Changes requested')",(uid,)).fetchone()
    def _tasks(self,c,uid,pid):
        if c.execute('SELECT 1 FROM tasks WHERE user_id=? AND project_id=?',(uid,pid)).fetchone():return
        for i,title in enumerate(STAGES):c.execute('INSERT INTO tasks(user_id,project_id,title,deadline) VALUES (?,?,?,?)',(uid,pid,title,(date.today()+timedelta(days=[7,28,35,42,49][i])).isoformat()))
    def notify(self,c,uid,title,message,dedupe=None):c.execute('INSERT OR IGNORE INTO notifications(user_id,title,message,created,dedupe) VALUES (?,?,?,?,?)',(uid,title,message,self.now(),dedupe))
    def _assign(self,c,uid,pid):
        c.execute('INSERT OR REPLACE INTO enrollments VALUES (?,?,?)',(uid,pid,self.now()));c.execute('DELETE FROM waitlist WHERE user_id=?',(uid,));self._tasks(c,uid,pid)
        self.notify(c,uid,'Project assigned','Your current project is '+c.execute('SELECT title FROM projects WHERE id=?',(pid,)).fetchone()[0])

    def select(self,pid):
        uid=self.auth()
        if self.user['role']!='student':raise RuleError('Only students can select.')
        with self.transaction() as c:
            p=self._open(c,pid)
            if p['selection_mode']!='Direct':raise RuleError('This project requires a proposal and supervisor approval.')
            if self._pending(c,uid):raise RuleError('Withdraw or resolve your pending application first.')
            old=c.execute('SELECT project_id FROM enrollments WHERE user_id=?',(uid,)).fetchone()
            if old and old[0]==pid:raise RuleError('You already selected this project.')
            if c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]>=p['capacity']:raise RuleError('Project full. Join its waitlist.')
            self._assign(c,uid,pid)
            if old:self.promote(c,old[0])
            self.log(c,uid,'Selected: '+p['title'])

    def wait(self,pid):
        uid=self.auth()
        if self.user['role']!='student':raise RuleError('Student access required.')
        with self.transaction() as c:
            if c.execute('SELECT 1 FROM waitlist WHERE user_id=? AND project_id=?',(uid,pid)).fetchone():
                c.execute('DELETE FROM waitlist WHERE user_id=? AND project_id=?',(uid,pid));self.log(c,uid,'Left waitlist');return
        with self.connect() as c:
            p=self._open(c,pid)
            if p['selection_mode']!='Direct':raise RuleError('Waitlists are available only for Direct selection projects.')
            if self._pending(c,self.auth()):raise RuleError('Resolve your pending application first.')
        return super().wait(pid)

    def promote(self,c,pid):
        p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not p or 'selection_mode' not in p.keys() or p['selection_mode']!='Direct' or p['status']!='Open' or p['deadline']<date.today().isoformat():return
        try:self._window(c)
        except RuleError:return
        while c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]<p['capacity']:
            w=c.execute('SELECT * FROM waitlist WHERE project_id=? ORDER BY id LIMIT 1',(pid,)).fetchone()
            if not w:break
            c.execute('DELETE FROM waitlist WHERE id=?',(w['id'],));uid=w['user_id']
            if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(uid,)).fetchone() or self._pending(c,uid) or c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(uid,)).fetchone():continue
            self._assign(c,uid,pid);self.log(c,uid,'Assigned from waitlist: '+p['title'])

    def team(self):
        uid=self.auth()
        with self.connect() as c:
            t=c.execute('SELECT t.* FROM teams t JOIN members m ON m.team_id=t.id WHERE m.user_id=?',(uid,)).fetchone()
            if not t:return None
            result=dict(t);result['members']=[dict(r) for r in c.execute('SELECT u.id,u.name,m.role FROM members m JOIN users u ON u.id=m.user_id WHERE m.team_id=?',(t['id'],))];return result
    def _team_mutable(self,c,tid):
        for r in c.execute('SELECT user_id FROM members WHERE team_id=?',(tid,)):
            if self._pending(c,r[0]) or c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(r[0],)).fetchone():raise RuleError('Team membership is locked while a member is assigned or has an active application.')
    def create_team(self,name):
        uid=self.auth()
        if self.user['role']!='student':raise RuleError('Student access required.')
        if self.team():raise RuleError('Leave your current team first.')
        with self.transaction() as c:
            if self._pending(c,uid) or c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(uid,)).fetchone():raise RuleError('Resolve your current assignment/application first.')
            tid=c.execute('INSERT INTO teams(name,leader_id) VALUES (?,?)',(required(name,'Team name'),uid)).lastrowid;c.execute('INSERT INTO members VALUES (?,?,?)',(tid,uid,'Leader'));self.log(c,uid,'Created team: '+name)
    def invite(self,invitee,role='Developer'):
        uid=self.auth();t=self.team()
        if not t or t['leader_id']!=uid:raise RuleError('Only the team leader can invite members.')
        with self.transaction() as c:
            self._team_mutable(c,t['id']);r=c.execute("SELECT id FROM users WHERE id=? AND role='student' AND active=1",(invitee.strip(),)).fetchone()
            if not r:raise RuleError('Active student account not found.')
            target=r[0]
            if c.execute('SELECT 1 FROM members WHERE user_id=?',(target,)).fetchone():raise RuleError('This student already belongs to a team.')
            c.execute("INSERT INTO invitations(team_id,invitee,status) VALUES (?,?,'Pending') ON CONFLICT(team_id,invitee) DO UPDATE SET status='Pending'",(t['id'],target));self.notify(c,target,'Team invitation','You were invited to '+t['name'])
    def invitations(self):
        uid=self.auth()
        with self.connect() as c:return [dict(r) for r in c.execute("SELECT i.*,t.name team FROM invitations i JOIN teams t ON t.id=i.team_id WHERE i.invitee=? AND i.status='Pending'",(uid,))]
    def respond_invite(self,iid,accept):
        uid=self.auth()
        with self.transaction() as c:
            r=c.execute("SELECT * FROM invitations WHERE id=? AND invitee=? AND status='Pending'",(iid,uid)).fetchone()
            if not r:raise RuleError('Invitation no longer available.')
            if accept:
                self._team_mutable(c,r['team_id'])
                if c.execute('SELECT 1 FROM members WHERE user_id=?',(uid,)).fetchone() or self._pending(c,uid) or c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(uid,)).fetchone():raise RuleError('Resolve your team, assignment or application before joining.')
                c.execute('INSERT INTO members VALUES (?,?,?)',(r['team_id'],uid,'Developer'))
            c.execute('UPDATE invitations SET status=? WHERE id=?',('Accepted' if accept else 'Declined',iid));self.log(c,uid,'Responded to team invitation')
    def team_role(self,member,role):
        uid=self.auth();t=self.team()
        if not t or t['leader_id']!=uid:raise RuleError('Only the leader can set member roles.')
        if member==uid:raise RuleError('The team leader keeps the Leader role.')
        with self.transaction() as c:c.execute('UPDATE members SET role=? WHERE team_id=? AND user_id=?',(required(role,'Role',50),t['id'],member))
    def leave_team(self):
        uid=self.auth();t=self.team()
        if not t:raise RuleError('You are not in a team.')
        with self.transaction() as c:
            self._team_mutable(c,t['id'])
            if t['leader_id']==uid:
                if len(t['members'])>1:raise RuleError('Other members must leave before the leader can dissolve the team.')
                c.execute('DELETE FROM teams WHERE id=?',(t['id'],))
            else:c.execute('DELETE FROM members WHERE user_id=?',(uid,))
            self.log(c,uid,'Left team')

    def apply(self,pid,proposal):
        uid=self.auth()
        if self.user['role']!='student':raise RuleError('Student access required.')
        t=self.team()
        if t and t['leader_id']!=uid:raise RuleError('Your team leader must submit the team application.')
        members=[m['id'] for m in t['members']] if t else [uid]
        with self.transaction() as c:
            p=self._open(c,pid)
            if p['selection_mode']!='Approval':raise RuleError('Use Direct selection for this project.')
            if len(members)>p['capacity']:raise RuleError('The team exceeds this project\'s total capacity.')
            for member in members:
                if self._pending(c,member) or c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(member,)).fetchone():raise RuleError('Every applicant must be unassigned and free of active applications.')
                if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(member,)).fetchone():raise RuleError('Every team member must have an active account.')
            aid=c.execute("INSERT INTO applications(project_id,applicant_id,team_id,proposal,status,created,team_name) VALUES (?,?,?,?,'Pending',?,?)",(pid,uid,t['id'] if t else None,required(proposal,'Proposal',5000),self.now(),t['name'] if t else 'Individual')).lastrowid
            for member in members:c.execute('INSERT INTO application_members VALUES (?,?)',(aid,member));c.execute('DELETE FROM waitlist WHERE user_id=?',(member,));self.notify(c,member,'Application submitted',p['title'])
            self.notify(c,p['owner_id'],'New application',p['title']);self.log(c,uid,'Applied to: '+p['title']);return aid
    def applications(self):
        uid=self.auth();role=self.user['role']
        with self.connect() as c:return [dict(r) for r in c.execute('''SELECT a.*,p.title,p.owner_id,u.name applicant,COALESCE(NULLIF(a.team_name,''),t.name,'Individual') team,(SELECT COUNT(*) FROM application_members m WHERE m.application_id=a.id) member_count FROM applications a JOIN projects p ON p.id=a.project_id JOIN users u ON u.id=a.applicant_id LEFT JOIN teams t ON t.id=a.team_id WHERE ?='admin' OR (?='teacher' AND p.owner_id=?) OR EXISTS(SELECT 1 FROM application_members m WHERE m.application_id=a.id AND m.user_id=?) ORDER BY a.id DESC''',(role,role,uid,uid))]
    def review_application(self,aid,decision,feedback=''):
        uid=self.auth(True)
        if decision not in ('Approved','Rejected','Changes requested'):raise RuleError('Invalid decision.')
        if decision!='Approved':feedback=required(feedback,'Feedback',3000)
        with self.transaction() as c:
            a=c.execute('SELECT * FROM applications WHERE id=?',(aid,)).fetchone()
            if not a or a['status'] not in ACTIVE_APPLICATIONS:raise RuleError('Application is no longer active.')
            p=self._owner(c,a['project_id']);members=[r[0] for r in c.execute('SELECT user_id FROM application_members WHERE application_id=?',(aid,))]
            if decision=='Approved':
                self._open(c,p['id'])
                if p['capacity']-c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(p['id'],)).fetchone()[0]<len(members):raise RuleError('There are not enough seats for the entire application.')
                for member in members:
                    if not c.execute('SELECT 1 FROM users WHERE id=? AND active=1',(member,)).fetchone() or c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(member,)).fetchone():raise RuleError('An applicant is disabled or already assigned. No assignments were changed.')
                for member in members:self._assign(c,member,p['id'])
            c.execute('UPDATE applications SET status=?,feedback=? WHERE id=?',(decision,feedback,aid))
            for member in members:self.notify(c,member,'Application '+decision.lower(),p['title']+' | '+feedback)
            self.log(c,uid,f'Application #{aid}: {decision}')
    def resubmit(self,aid,proposal):
        uid=self.auth()
        with self.transaction() as c:
            a=c.execute('SELECT * FROM applications WHERE id=?',(aid,)).fetchone()
            if not a or a['applicant_id']!=uid or a['status']!='Changes requested':raise RuleError('Only the applicant can resubmit a returned application.')
            self._open(c,a['project_id']);c.execute("UPDATE applications SET proposal=?,status='Pending' WHERE id=?",(required(proposal,'Proposal',5000),aid));p=c.execute('SELECT owner_id,title FROM projects WHERE id=?',(a['project_id'],)).fetchone();self.notify(c,p[0],'Application resubmitted',p[1]);self.log(c,uid,'Resubmitted application #'+str(aid))
    def withdraw(self,aid):
        uid=self.auth()
        with self.transaction() as c:
            a=c.execute('SELECT * FROM applications WHERE id=?',(aid,)).fetchone()
            if not a or a['applicant_id']!=uid or a['status'] not in ACTIVE_APPLICATIONS:raise RuleError('Only the applicant can withdraw an active application.')
            c.execute("UPDATE applications SET status='Withdrawn' WHERE id=?",(aid,));self.log(c,uid,'Withdrew application #'+str(aid))

    def tasks(self):
        uid=self.auth();role=self.user['role']
        with self.connect() as c:return [dict(r) for r in c.execute('''SELECT t.*,p.title project,u.name student FROM tasks t JOIN projects p ON p.id=t.project_id JOIN users u ON u.id=t.user_id JOIN enrollments e ON e.user_id=t.user_id AND e.project_id=t.project_id WHERE ?='admin' OR (?='teacher' AND p.owner_id=?) OR (?='student' AND t.user_id=?) ORDER BY t.deadline,t.id''',(role,role,uid,role,uid))]
    def update_task(self,tid,status):
        uid=self.auth()
        if status not in ('Todo','In progress','Done'):raise RuleError('Invalid milestone status.')
        with self.transaction() as c:
            r=c.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if not r or not any(t['id']==tid for t in self.tasks()):raise RuleError('Milestone not available.')
            if self.user['role']=='student' and r['user_id']!=uid:raise RuleError('This milestone belongs to another student.')
            c.execute('UPDATE tasks SET status=? WHERE id=?',(status,tid));self.log(c,uid,'Milestone '+status+': '+r['title'])
    def add_task(self,pid,title,deadline):
        uid=self.auth(True)
        try:deadline=date.fromisoformat(deadline).isoformat()
        except ValueError:raise RuleError('Use YYYY-MM-DD.') from None
        with self.transaction() as c:
            self._owner(c,pid);members=c.execute('SELECT user_id FROM enrollments WHERE project_id=?',(pid,)).fetchall()
            if not members:raise RuleError('This project has no assigned students.')
            for m in members:c.execute('INSERT INTO tasks(user_id,project_id,title,deadline) VALUES (?,?,?,?)',(m[0],pid,required(title,'Milestone title'),deadline));self.notify(c,m[0],'Milestone added',title+' | '+deadline)
            self.log(c,uid,'Added milestone: '+title)
    def submissions(self):
        uid=self.auth();role=self.user['role']
        with self.connect() as c:return [dict(r) for r in c.execute('''SELECT s.*,p.title project,u.name student FROM submissions s JOIN projects p ON p.id=s.project_id JOIN users u ON u.id=s.user_id WHERE ?='admin' OR (?='teacher' AND p.owner_id=?) OR (?='student' AND s.user_id=?) ORDER BY s.id DESC''',(role,role,uid,role,uid))]
    def submit(self,title,link='',notes='',attachment=''):
        uid=self.auth()
        if self.user['role']!='student':raise RuleError('Student access required.')
        pid=self.selected()
        if not pid:raise RuleError('Select a project before submitting work.')
        if link and (urlparse(link).scheme not in ('http','https') or not urlparse(link).netloc):raise RuleError('Use a complete https:// or http:// link.')
        if not link and not attachment:raise RuleError('Add a document attachment or a code/report link.')
        copied=None;filename='';relative=''
        try:
            if attachment:
                source=Path(attachment)
                if source.suffix.lower() not in ('.pdf','.docx','.txt','.png','.jpg','.jpeg','.zip') or source.stat().st_size>20*1024*1024:raise RuleError('Attach a PDF, DOCX, TXT, image or ZIP up to 20 MB.')
                folder=self.path.parent/'attachments';folder.mkdir(exist_ok=True);copied=folder/(secrets.token_hex(16)+source.suffix.lower());shutil.copy2(source,copied);filename=source.name;relative='attachments/'+copied.name
            with self.transaction() as c:
                p=c.execute('SELECT owner_id,title FROM projects WHERE id=?',(pid,)).fetchone()
                c.execute('INSERT INTO submissions(user_id,project_id,title,link,attachment,filename,notes,created) VALUES (?,?,?,?,?,?,?,?)',(uid,pid,required(title,'Submission title'),link,relative,filename,notes[:5000],self.now()));self.notify(c,p[0],'New submission',title+' | '+self.user['name']);self.log(c,uid,'Submitted: '+title)
        except Exception:
            if copied:copied.unlink(missing_ok=True)
            raise
    def review_submission(self,sid,status,feedback):
        uid=self.auth(True)
        if status not in ('Accepted','Changes requested'):raise RuleError('Choose Accepted or Changes requested.')
        with self.transaction() as c:
            r=c.execute('SELECT * FROM submissions WHERE id=?',(sid,)).fetchone()
            if not r:raise RuleError('Submission no longer exists.')
            self._owner(c,r['project_id']);c.execute('UPDATE submissions SET status=?,feedback=? WHERE id=?',(status,required(feedback,'Feedback',3000),sid));self.notify(c,r['user_id'],'Submission '+status.lower(),r['title']+' | '+feedback);self.log(c,uid,'Reviewed submission #'+str(sid))
    def attachment_path(self,sid):
        r=next((r for r in self.submissions() if r['id']==sid),None)
        if not r or not r['attachment']:raise RuleError('This submission has no attachment.')
        path=(self.path.parent/r['attachment']).resolve()
        if not path.is_relative_to((self.path.parent/'attachments').resolve()) or not path.is_file():raise RuleError('Attachment file not found.')
        return path
    def notifications(self):
        uid=self.auth()
        with self.transaction() as c:
            for p in c.execute('SELECT id FROM projects').fetchall():self.promote(c,p[0])
            for t in self.tasks():
                if t['user_id']==uid and t['status']!='Done' and t['deadline']<=(date.today()+timedelta(days=7)).isoformat():self.notify(c,uid,'Milestone due',t['title']+' | '+t['deadline'],'task:'+str(t['id']))
            for p in self.projects():
                if p['status']=='Open' and p['deadline']<= (date.today()+timedelta(days=7)).isoformat() and p['deadline']>=date.today().isoformat():self.notify(c,uid,'Selection deadline',p['title']+' | '+p['deadline'],uid+':project:'+str(p['id']))
            return [dict(r) for r in c.execute('SELECT * FROM notifications WHERE user_id=? ORDER BY id DESC LIMIT 200',(uid,))]
    def read_notifications(self):
        uid=self.auth()
        with self.transaction() as c:c.execute('UPDATE notifications SET is_read=1 WHERE user_id=?',(uid,))

    def preview_import(self,path,kind,password=''):
        self.auth(True)
        if kind=='students':self.auth(admin=True);valid_password(password)
        with Path(path).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        if not rows or len(rows)>2000:raise RuleError('Import 1–2,000 rows at a time.')
        clean=[];seen=set()
        for i,r in enumerate(rows,2):
            try:
                if kind=='students':
                    uid=required(r.get('id',r.get('student_id','')),'ID',40)
                    if uid.casefold() in seen:raise RuleError('Duplicate account in CSV.')
                    seen.add(uid.casefold());valid_password(r.get('password') or password)
                    clean.append(dict(id=uid,name=required(r.get('name',r.get('student_name','')),'Name'),major=required(r.get('major',''),'Major'),password=r.get('password') or password))
                else:
                    title=required(r.get('title',r.get('project_name','')),'Title')
                    if 'capacity' not in r and 'remaining_team_members' in r:raise RuleError('Use paired legacy migration for remaining-seat data.')
                    capacity=int(r.get('capacity',r.get('remaining_team_members',0)));deadline=date.fromisoformat(r.get('deadline') or (date.today()+timedelta(days=30)).isoformat()).isoformat()
                    if not 1<=capacity<=10000:raise RuleError('Capacity must be 1–10,000.')
                    status=r.get('status') or 'Open';mode=r.get('selection_mode') or 'Approval'
                    if status not in ('Draft','Open','Closed') or mode not in ('Direct','Approval'):raise RuleError('Invalid status / mode.')
                    clean.append(dict(title=title,supervisor=required(r.get('supervisor',r.get('supervisor_name',self.user['name'])),'Supervisor'),description=r.get('description') or 'Imported project',category=r.get('category') or 'Imported',capacity=capacity,deadline=deadline,status=status,selection_mode=mode,owner_id=self.user['id']))
            except (ValueError,TypeError) as e:raise RuleError(f'CSV line {i}: {e}') from None
        return dict(kind=kind,rows=clean)
    def commit_import(self,preview):
        uid=self.auth(True);kind=preview['kind']
        if kind=='students':self.auth(admin=True)
        with self.transaction() as c:
            for r in preview['rows']:
                if kind=='students':
                    if c.execute('SELECT 1 FROM users WHERE id=?',(r['id'],)).fetchone():raise RuleError('Account already exists: '+r['id'])
                    valid_password(r['password']);c.execute("INSERT INTO users(id,name,major,role,password,active) VALUES (?,?,?,'student',?,1)",(r['id'],r['name'],r['major'],password_hash(r['password'])))
                else:
                    keys=['title','supervisor','description','category','capacity','deadline','status','selection_mode','owner_id'];c.execute('INSERT INTO projects('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[r[k] for k in keys])
            self.log(c,uid,f"Imported {len(preview['rows'])} {kind}")
        return len(preview['rows'])
    def backup_bundle(self,path):
        self.auth(admin=True);self.validate_output(path)
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'workspace.db'
            with self.connect() as source,sqlite3.connect(target) as dest:source.backup(dest)
            with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
                z.write(target,'workspace.db')
                for f in (self.path.parent/'attachments').glob('*'):
                    if f.is_file():z.write(f,'attachments/'+f.name)
    def report_lines(self,kind):
        self.auth();projects=self.projects();students=self.students();tasks=self.tasks()
        if kind=='Assignments':return [f"{r['name']} ({r['id']}) | {r['major']} | {r['project']}" for r in students]
        if kind=='Progress':return [f"{r['student']} | {r['project']} | {r['title']} | {r['status']} | Due {r['deadline']}" for r in tasks]
        if kind=='Workload':
            self.auth(True);return [f"{p['supervisor']} | {p['title']} | {p['enrolled']}/{p['capacity']} students | {sum(t['status']=='Done' for t in tasks if t['project_id']==p['id'])} milestones completed" for p in projects]
        return [f"{p['title']} | {p['supervisor']} | {p['enrolled']}/{p['capacity']} assigned | {p['selection_mode']} | Due {p['deadline']}" for p in projects]

    def preview_legacy(self,project_path,student_path,password,deadline):
        self.auth(admin=True);valid_password(password)
        try:deadline=date.fromisoformat(deadline).isoformat()
        except ValueError:raise RuleError('Use YYYY-MM-DD.') from None
        with Path(project_path).open(encoding='utf-8-sig',newline='') as f:projects=list(csv.DictReader(f))
        with Path(student_path).open(encoding='utf-8-sig',newline='') as f:students=list(csv.DictReader(f))
        if not projects or len(projects)+len(students)>2000:raise RuleError('Migration requires projects and at most 2,000 total rows.')
        seen=set();pids={};clean_students=[]
        for r in students:
            uid=required(r.get('student_id',''),'Student ID',40)
            if not all(x.isalnum() or x in '._-' for x in uid) or uid.casefold() in seen:raise RuleError('Invalid or duplicate student ID: '+uid)
            seen.add(uid.casefold());selected=(r.get('selected_project_id') or '').strip()
            clean_students.append(dict(id=uid,name=required(r.get('student_name',''),'Student name'),major=required(r.get('major',''),'Major'),selected=selected if selected not in ('NULL','null','None','0') else '',password=password))
        for r in projects:
            old=required(r.get('project_id',''),'Project ID',40)
            if old in pids:raise RuleError('Duplicate legacy project ID.')
            try:remaining=int(r['remaining_team_members'])
            except (ValueError,KeyError):raise RuleError('Invalid remaining seat count.') from None
            count=sum(s['selected']==old for s in clean_students)
            if remaining<0 or not 1<=remaining+count<=10000:raise RuleError('Invalid total capacity for legacy project '+old)
            pids[old]=dict(title=required(r.get('project_name',''),'Project title'),supervisor=required(r.get('supervisor_name',''),'Supervisor'),category='Migrated',description='Migrated from the original Java/MySQL application.',capacity=remaining+count,deadline=deadline,status='Open',selection_mode='Direct',owner_id=self.user['id'])
        for s in clean_students:
            if s['selected'] and s['selected'] not in pids:raise RuleError('Unknown selected project for student '+s['id'])
        return dict(kind='legacy',projects=pids,students=clean_students,rows=[dict(title=p['title'],capacity=p['capacity'],id=k) for k,p in pids.items()]+[dict(id=s['id'],name=s['name'],selected=s['selected']) for s in clean_students])

    def commit_legacy(self,preview):
        uid=self.auth(admin=True)
        with self.transaction() as c:
            for r in preview['students']:
                if c.execute('SELECT 1 FROM users WHERE id=?',(r['id'],)).fetchone():raise RuleError('Account already exists: '+r['id'])
            mapping={}
            for old,p in preview['projects'].items():
                keys=list(p);mapping[old]=c.execute('INSERT INTO projects('+','.join(keys)+') VALUES ('+','.join('?' for _ in keys)+')',[p[k] for k in keys]).lastrowid
            for r in preview['students']:
                c.execute("INSERT INTO users(id,name,major,role,password,active) VALUES (?,?,?,'student',?,1)",(r['id'],r['name'],r['major'],password_hash(r['password'])))
                if r['selected']:self._assign(c,r['id'],mapping[r['selected']])
            self.log(c,uid,'Migrated legacy projects, students and assignments')
        return len(preview['rows'])

    def backup(self,path):
        self.auth(admin=True)
        return super().backup(path)

    def validate_output(self,path):
        target=Path(path).resolve()
        if target==self.path.resolve() or target.is_relative_to((self.path.parent/'attachments').resolve()):raise RuleError('Choose an output outside the live workspace files and attachments.')
    def export(self,path,kind):
        self.validate_output(path)
        if kind=='json':
            self.auth();data={'version':'3.0.1','projects':self.projects(),'students':self.students(),'activity':self.activity(),'applications':self.applications(),'milestones':self.tasks(),'submissions':[{k:v for k,v in r.items() if k!='attachment'} for r in self.submissions()]}
            Path(path).write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8');return
        return super().export(path,kind)
