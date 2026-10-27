import csv
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path
from datetime import date, timedelta
from projectpilot.service import Service, RuleError

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'workspace.db';self.s=Service(self.path);self.s.login('teacher','DemoPass123!')
    def tearDown(self):self.temp.cleanup()
    def project(self,**changes):
        p=dict(title='Test project',supervisor='Dr Test',category='Testing',description='A real test project.',capacity=1,deadline=(date.today()+timedelta(days=10)).isoformat(),status='Open');p.update(changes);return self.s.save_project(p)
    def student(self,uid='student'):self.s.login(uid,'DemoPass123!')
    def test_login_case_insensitive_and_bad_password(self):
        self.s.login('TEACHER','DemoPass123!');self.assertEqual(self.s.user['role'],'teacher')
        with self.assertRaises(RuleError):self.s.login('teacher','wrong')
    def test_registration_and_duplicate(self):
        self.s.register('new','New Student','CS','LongPass123!');self.s.login('new','LongPass123!');self.assertEqual(self.s.user['name'],'New Student')
        with self.assertRaises(RuleError):self.s.register('NEW','X','CS','LongPass123!')
        with self.assertRaises(RuleError):self.s.register('bad id','X','CS','LongPass123!')
    def test_weak_password_rejected(self):
        with self.assertRaises(RuleError):self.s.register('x','X','CS','short')
    def test_role_boundaries_and_draft_visibility(self):
        pid=self.project(status='Draft');self.student();self.assertNotIn(pid,[p['id'] for p in self.s.projects()])
        with self.assertRaises(RuleError):self.s.delete_project(1)
        with self.assertRaises(RuleError):self.s.save_project({})
        self.assertEqual(len(self.s.students()),1)
    def test_selection_idempotency_and_capacity(self):
        pid=self.project();self.student();self.s.select(pid)
        with self.assertRaises(RuleError):self.s.select(pid)
        self.student('student2')
        with self.assertRaises(RuleError):self.s.select(pid)
        self.assertEqual(next(p for p in self.s.projects() if p['id']==pid)['available'],0)
    def test_failed_switch_keeps_old_assignment(self):
        pid=self.project();self.student();self.s.select(pid);self.student('student2');old=self.s.selected()
        with self.assertRaises(RuleError):self.s.select(pid)
        self.assertEqual(self.s.selected(),old)
    def test_successful_switch_releases_old_seat(self):
        a=self.project();b=self.project(title='Second');self.student();self.s.select(a);self.s.select(b)
        self.assertEqual(self.s.selected(),b);self.assertEqual(next(p for p in self.s.projects() if p['id']==a)['available'],1)
    def test_waitlist_promotion(self):
        pid=self.project();self.student();self.s.select(pid);self.student('student2');self.s.cancel();self.s.wait(pid)
        self.student();self.s.cancel();self.student('student2');self.assertEqual(self.s.selected(),pid)
        self.assertFalse(next(p for p in self.s.projects() if p['id']==pid)['waiting'])
    def test_waitlist_fifo_and_multiple_lists_removed(self):
        a=self.project();b=self.project(title='Second');self.student();self.s.select(a)
        self.student('student2');self.s.cancel();self.s.select(b)
        self.student('student3');self.s.cancel();self.s.wait(a);self.s.wait(b)
        self.student();self.s.cancel();self.student('student3');self.assertEqual(self.s.selected(),a);self.assertFalse(any(p['waiting'] for p in self.s.projects()))
    def test_expired_closed_draft_block_selection(self):
        ids=[self.project(deadline=(date.today()-timedelta(days=1)).isoformat()),self.project(status='Closed'),self.project(status='Draft')]
        self.student()
        for pid in ids:
            with self.assertRaises(RuleError):self.s.select(pid)
    def test_invalid_project_input(self):
        for change in [dict(capacity=0),dict(deadline='not-date'),dict(status='bad'),dict(title='')]:
            with self.assertRaises(RuleError):self.project(**change)
    def test_edit_capacity_and_draft_guards(self):
        p=next(p for p in self.s.projects() if p['id']==1);p['capacity']=2;self.s.save_project(p,1)
        self.student();self.s.select(1);self.s.login('teacher','DemoPass123!');p['capacity']=1
        with self.assertRaises(RuleError):self.s.save_project(p,1)
        p['capacity']=2;p['status']='Draft'
        with self.assertRaises(RuleError):self.s.save_project(p,1)
    def test_delete_releases_students(self):
        self.s.delete_project(1);self.student('student2');self.assertIsNone(self.s.selected())
    def test_favorites_and_scope(self):
        self.student();self.s.favorite(1);self.assertTrue(self.s.projects()[0]['favorite']);self.s.favorite(1);self.assertFalse(self.s.projects()[0]['favorite'])
        self.s.select(1);self.assertTrue(all(e['actor']=='student' for e in self.s.activity()))
    def test_password_change(self):
        self.s.change_password('DemoPass123!','NewPass123!')
        with self.assertRaises(RuleError):self.s.login('teacher','DemoPass123!')
        self.s.login('teacher','NewPass123!')
    def test_export_scope_and_formula_escaping(self):
        self.project(title='=1+1');path=Path(self.temp.name)/'export.csv';self.s.export(path,'csv');self.assertIn("'=1+1",path.read_text(encoding='utf-8-sig'))
        self.student();path=Path(self.temp.name)/'export.json';self.s.export(path,'json');payload=json.loads(path.read_text());self.assertEqual(len(payload['students']),1);self.assertNotIn('password',path.read_text());self.assertNotIn('DemoPass',path.read_text())
        with self.assertRaises(RuleError):self.s.export(self.path,'json')
    def test_backup_and_restart(self):
        path=Path(self.temp.name)/'backup.db';self.s.backup(path);new=Service(path);new.login('teacher','DemoPass123!');self.assertEqual(len(new.projects()),6)
        self.student()
        with self.assertRaises(RuleError):self.s.backup(path)
    def test_concurrent_last_seat(self):
        pid=self.project();self.s.register('one','One','CS','LongPass123!');self.s.register('two','Two','CS','LongPass123!');barrier=threading.Barrier(2);results=[]
        def select(uid):
            s=Service(self.path);s.login(uid,'LongPass123!');barrier.wait()
            try:s.select(pid);results.append('ok')
            except RuleError:results.append('full')
        threads=[threading.Thread(target=select,args=(u,)) for u in ['one','two']]
        for t in threads:t.start()
        for t in threads:t.join()
        self.assertCountEqual(results,['ok','full'])

if __name__=='__main__':unittest.main()
