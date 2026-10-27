"""Application rules and transactional SQLite persistence; independent of Tk."""
from __future__ import annotations
import csv
import hashlib
import hmac
import io
import json
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

ITERATIONS = 210_000

class RuleError(ValueError):
    """A user-correctable business-rule failure."""

def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), ITERATIONS).hex()

def verify_password(password, encoded):
    return hmac.compare_digest(password_hash(password, encoded.split(':')[0]), encoded)

def valid_password(password):
    if len(password) < 8 or len(password) > 128:
        raise RuleError('Use a password with 8–128 characters.')

def required(value, label, limit=120):
    value = str(value).strip()
    if not value or len(value) > limit:
        raise RuleError(f'{label} is required (maximum {limit} characters).')
    return value

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try: return super().__exit__(*args)
        finally: self.close()

class Service:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY COLLATE NOCASE, name TEXT NOT NULL, major TEXT NOT NULL,
              role TEXT NOT NULL CHECK(role IN ('teacher','student')), password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS projects (
              id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, supervisor TEXT NOT NULL,
              category TEXT NOT NULL, description TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity>0),
              deadline TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('Draft','Open','Closed')));
            CREATE TABLE IF NOT EXISTS enrollments (
              user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
              project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS favorites (
              user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
              project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE, PRIMARY KEY(user_id,project_id));
            CREATE TABLE IF NOT EXISTS waitlist (
              id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
              project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE, UNIQUE(user_id,project_id));
            CREATE TABLE IF NOT EXISTS activity (
              id INTEGER PRIMARY KEY, actor TEXT NOT NULL, message TEXT NOT NULL, created TEXT NOT NULL);
            ''')
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
                for uid, name, role, major in [('teacher','Demo Supervisor','teacher','Faculty'),('student','Demo Student','student','Software Engineering'),('student2','Alex Chen','student','Computer Science'),('student3','Sam Lee','student','Information Systems')]:
                    c.execute('INSERT INTO users VALUES (?,?,?,?,?)', (uid,name,major,role,password_hash('DemoPass123!')))
                seeds = json.loads((Path(__file__).parent/'seed.json').read_text(encoding='utf-8'))
                for p in seeds:
                    p['deadline'] = (date.today()+timedelta(days=p.pop('days'))).isoformat()
                    c.execute('INSERT INTO projects(title,supervisor,category,description,capacity,deadline,status) VALUES (:title,:supervisor,:category,:description,:capacity,:deadline,:status)',p)
                c.execute('INSERT INTO enrollments VALUES (?,?,?)',('student2',1,self.now()))
                c.execute('INSERT INTO enrollments VALUES (?,?,?)',('student3',3,self.now()))
                self.log(c,'system','Demo workspace initialized')
        self.user = None

    def connect(self):
        c=sqlite3.connect(self.path,timeout=15,factory=ClosingConnection)
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c

    @staticmethod
    def now(): return datetime.now().isoformat(timespec='seconds')

    @contextmanager
    def transaction(self):
        c=self.connect()
        try:
            c.execute('BEGIN IMMEDIATE')
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally: c.close()

    def log(self,c,actor,message):
        c.execute('INSERT INTO activity(actor,message,created) VALUES (?,?,?)',(actor,message,self.now()))

    def auth(self,teacher=False):
        if not self.user: raise RuleError('Sign in first.')
        if teacher and self.user['role']!='teacher': raise RuleError('Only supervisors can do this.')
        return self.user['id']

    def login(self,uid,password):
        with self.connect() as c:
            r=c.execute('SELECT * FROM users WHERE id=?',(uid.strip(),)).fetchone()
        if not r or not verify_password(password,r['password']):
            raise RuleError('Incorrect account ID or password.')
        self.user={k:r[k] for k in ('id','name','major','role')}
        return self.user

    def register(self,uid,name,major,password):
        uid=required(uid,'Account ID',40)
        if not all(c.isalnum() or c in '._-' for c in uid): raise RuleError('Account ID: use letters, numbers, dot, underscore or hyphen.')
        name=required(name,'Name');major=required(major,'Major');valid_password(password)
        try:
            with self.transaction() as c:
                c.execute('INSERT INTO users VALUES (?,?,?,?,?)',(uid,name,major,'student',password_hash(password)))
                self.log(c,uid,'Student account created')
        except sqlite3.IntegrityError: raise RuleError('That account ID is already registered.') from None

    def change_password(self,old,new):
        uid=self.auth();valid_password(new)
        with self.transaction() as c:
            p=c.execute('SELECT password FROM users WHERE id=?',(uid,)).fetchone()[0]
            if not verify_password(old,p): raise RuleError('Current password is incorrect.')
            c.execute('UPDATE users SET password=? WHERE id=?',(password_hash(new),uid))
            self.log(c,uid,'Password changed')

    def projects(self):
        uid=self.auth()
        with self.connect() as c:
            return [dict(r) for r in c.execute('''SELECT p.*, COUNT(e.user_id) enrolled,
                p.capacity-COUNT(e.user_id) available,
                EXISTS(SELECT 1 FROM favorites f WHERE f.user_id=? AND f.project_id=p.id) favorite,
                EXISTS(SELECT 1 FROM waitlist w WHERE w.user_id=? AND w.project_id=p.id) waiting
                FROM projects p LEFT JOIN enrollments e ON e.project_id=p.id
                WHERE p.status!='Draft' OR ?='teacher' GROUP BY p.id ORDER BY p.id''',(uid,uid,self.user['role']))]

    def students(self):
        uid=self.auth()
        with self.connect() as c:
            return [dict(r) for r in c.execute('''SELECT u.id,u.name,u.major,e.project_id,
              COALESCE(p.title,'Unassigned') project FROM users u LEFT JOIN enrollments e ON u.id=e.user_id
              LEFT JOIN projects p ON p.id=e.project_id WHERE u.role='student' AND (?='teacher' OR u.id=?)
              ORDER BY u.name''',(self.user['role'],uid))]

    def activity(self):
        uid=self.auth()
        with self.connect() as c:
            return [dict(r) for r in c.execute("SELECT actor,message,created FROM activity WHERE ?='teacher' OR actor=? ORDER BY id DESC LIMIT 80",(self.user['role'],uid))]

    def selected(self):
        rows=self.students()
        return next((r['project_id'] for r in rows if r['id'].lower()==self.user['id'].lower()),None)

    def save_project(self,p,pid=None):
        uid=self.auth(True)
        p={k:p[k] for k in ('title','supervisor','category','description','capacity','deadline','status')}
        for k in ('title','supervisor','category'): p[k]=required(p[k],k.title())
        p['description']=required(p['description'],'Description',3000)
        try: p['capacity']=int(p['capacity'])
        except (ValueError,TypeError): raise RuleError('Capacity must be a whole number.') from None
        if not 1<=p['capacity']<=10000: raise RuleError('Capacity must be between 1 and 10,000.')
        try: p['deadline']=date.fromisoformat(p['deadline']).isoformat()
        except (ValueError,TypeError): raise RuleError('Use a valid deadline: YYYY-MM-DD.') from None
        if p['status'] not in ('Draft','Open','Closed'): raise RuleError('Invalid project status.')
        with self.transaction() as c:
            if pid:
                if not c.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone(): raise RuleError('Project no longer exists.')
                n=c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]
                if p['capacity']<n: raise RuleError('Capacity cannot be below the current enrollment.')
                if p['status']=='Draft' and n: raise RuleError('An assigned project cannot be changed to Draft. Use Closed instead.')
                c.execute('UPDATE projects SET '+','.join(k+'=:'+k for k in p)+' WHERE id=:id',dict(p,id=pid))
            else:
                pid=c.execute('INSERT INTO projects('+','.join(p)+') VALUES ('+','.join(':'+k for k in p)+')',p).lastrowid
            self.promote(c,pid)
            self.log(c,uid,('Updated: ' if 'id' in p else 'Saved: ')+p['title'])
        return pid

    def delete_project(self,pid):
        uid=self.auth(True)
        with self.transaction() as c:
            r=c.execute('SELECT title FROM projects WHERE id=?',(pid,)).fetchone()
            if not r: raise RuleError('Project no longer exists.')
            c.execute('DELETE FROM projects WHERE id=?',(pid,))
            self.log(c,uid,'Deleted project and released its students: '+r[0])

    def _open(self,c,pid):
        p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not p: raise RuleError('Project no longer exists.')
        if p['status']!='Open' or p['deadline']<date.today().isoformat(): raise RuleError('This project is closed or its deadline has passed.')
        return p

    def select(self,pid):
        uid=self.auth()
        if self.user['role']!='student': raise RuleError('Only students can select a project.')
        with self.transaction() as c:
            p=self._open(c,pid)
            old=c.execute('SELECT project_id FROM enrollments WHERE user_id=?',(uid,)).fetchone()
            if old and old[0]==pid: raise RuleError('You already selected this project.')
            n=c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]
            if n>=p['capacity']: raise RuleError('This project is full. You can join its waitlist.')
            c.execute('DELETE FROM enrollments WHERE user_id=?',(uid,))
            c.execute('INSERT INTO enrollments VALUES (?,?,?)',(uid,pid,self.now()))
            c.execute('DELETE FROM waitlist WHERE user_id=?',(uid,))
            if old: self.promote(c,old[0])
            self.log(c,uid,'Selected: '+p['title'])

    def cancel(self):
        uid=self.auth()
        if self.user['role']!='student': raise RuleError('Only students can cancel their selection.')
        with self.transaction() as c:
            old=c.execute('SELECT project_id FROM enrollments WHERE user_id=?',(uid,)).fetchone()
            if not old: raise RuleError('You have no active selection.')
            c.execute('DELETE FROM enrollments WHERE user_id=?',(uid,))
            self.log(c,uid,'Cancelled project selection')
            self.promote(c,old[0])

    def wait(self,pid):
        uid=self.auth()
        if self.user['role']!='student': raise RuleError('Only students can join a waitlist.')
        with self.transaction() as c:
            p=self._open(c,pid)
            if c.execute('SELECT 1 FROM waitlist WHERE user_id=? AND project_id=?',(uid,pid)).fetchone():
                c.execute('DELETE FROM waitlist WHERE user_id=? AND project_id=?',(uid,pid))
                self.log(c,uid,'Left waitlist: '+p['title']); return
            if c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(uid,)).fetchone(): raise RuleError('Cancel your current selection before joining a waitlist.')
            n=c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]
            if n<p['capacity']: raise RuleError('Seats are available. Select this project directly.')
            c.execute('INSERT INTO waitlist(user_id,project_id) VALUES (?,?)',(uid,pid))
            self.log(c,uid,'Joined waitlist: '+p['title'])

    def promote(self,c,pid):
        p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
        if not p or p['status']!='Open' or p['deadline']<date.today().isoformat(): return
        while c.execute('SELECT COUNT(*) FROM enrollments WHERE project_id=?',(pid,)).fetchone()[0]<p['capacity']:
            w=c.execute('SELECT * FROM waitlist WHERE project_id=? ORDER BY id LIMIT 1',(pid,)).fetchone()
            if not w: break
            uid=w['user_id']
            c.execute('DELETE FROM waitlist WHERE id=?',(w['id'],))
            if c.execute('SELECT 1 FROM enrollments WHERE user_id=?',(uid,)).fetchone(): continue
            c.execute('INSERT INTO enrollments VALUES (?,?,?)',(uid,pid,self.now()))
            c.execute('DELETE FROM waitlist WHERE user_id=?',(uid,))
            self.log(c,uid,'Automatically assigned from waitlist: '+p['title'])

    def favorite(self,pid):
        uid=self.auth()
        if not any(p['id']==pid for p in self.projects()): raise RuleError('Project is not available.')
        with self.transaction() as c:
            exists=c.execute('SELECT 1 FROM favorites WHERE user_id=? AND project_id=?',(uid,pid)).fetchone()
            if exists: c.execute('DELETE FROM favorites WHERE user_id=? AND project_id=?',(uid,pid))
            else: c.execute('INSERT INTO favorites VALUES (?,?)',(uid,pid))

    def export(self,path,kind):
        self.auth()
        data={'projects':self.projects(),'students':self.students(),'activity':self.activity()}
        path=Path(path)
        if path.resolve()==self.path.resolve(): raise RuleError('An export cannot replace the live database.')
        if kind=='json': path.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        else:
            rows=data['projects']
            with path.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]) if rows else ['id','title']);w.writeheader()
                for row in rows:
                    # Prevent spreadsheet formulas in user-provided text.
                    w.writerow({k: "'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for k,v in row.items()})

    def backup(self,path):
        self.auth(True)
        if Path(path).resolve()==self.path.resolve(): raise RuleError('Choose a different file for the backup.')
        with self.connect() as source, sqlite3.connect(path) as dest: source.backup(dest)
