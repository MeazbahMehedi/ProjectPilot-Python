import unittest,tempfile,csv,zipfile,json,sqlite3
from pathlib import Path
from datetime import date,timedelta
from projectpilot.advanced import Service
from projectpilot.service import Service as CoreService,RuleError
from projectpilot.reports import write_pdf

class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.s=Service(self.dir/'workspace.db');self.login('admin')
    def tearDown(self):self.tmp.cleanup()
    def login(self,uid):self.s.login(uid,'DemoPass123!')
    def project(self,**updates):
        p=dict(title='Advanced project',supervisor='Supervisor',category='Research',description='A project with an application workflow.',capacity=3,deadline=(date.today()+timedelta(days=20)).isoformat(),status='Open',selection_mode='Approval',owner_id='teacher');p.update(updates);return self.s.save_project(p)
    def add(self,uid,role='student'):self.s.manage_account(uid,uid.title(),'CS',role,'DemoPass123!',True)
    def team_application(self,pid):
        self.add('mate');self.login('student');self.s.create_team('Team Research');self.s.invite('mate');self.login('mate');self.s.respond_invite(self.s.invitations()[0]['id'],True);self.login('student');return self.s.apply(pid,'We will evaluate a reproducible research prototype.')
    def test_admin_bootstrap_once(self):
        self.assertEqual(sum(a['role']=='admin' for a in self.s.accounts()),1);new=Service(self.dir/'workspace.db');new.login('admin','DemoPass123!');self.assertEqual(sum(a['role']=='admin' for a in new.accounts()),1)
    def test_supervisor_ownership(self):
        self.add('advisor2','teacher');pid=self.project(owner_id='advisor2');self.login('teacher');self.assertNotIn(pid,[p['id'] for p in self.s.projects()])
        with self.assertRaises(RuleError):self.s.delete_project(pid)
        with self.assertRaises(RuleError):self.s.save_project(dict(title='x'),pid)
    def test_admin_self_lockout_guard(self):
        with self.assertRaises(RuleError):self.s.manage_account('admin','Admin','Admin','student','',False)
    def test_disable_account_and_reset_password(self):
        self.s.manage_account('student','Demo Student','CS','student','Changed123!',False)
        with self.assertRaises(RuleError):self.s.login('student','Changed123!')
        self.login('admin');self.s.manage_account('student','Demo Student','CS','student','',True);self.s.login('student','Changed123!')
    def test_live_role_revocation(self):
        self.add('other','teacher');other=Service(self.dir/'workspace.db');other.login('other','DemoPass123!');self.s.manage_account('other','Other','CS','student','',True)
        with self.assertRaises(RuleError):other.save_project({})
    def test_selection_period_closes_direct_and_approval(self):
        pid=self.project();self.s.save_settings(enabled='0');self.login('student')
        for fn in [lambda:self.s.select(1),lambda:self.s.apply(pid,'Research proposal'),lambda:self.s.wait(1)]:
            with self.assertRaises(RuleError):fn()
    def test_invalid_period(self):
        with self.assertRaises(RuleError):self.s.save_settings('2027-02-01','2027-01-01')
    def test_approval_cannot_bypass_via_direct_or_wait(self):
        pid=self.project();self.login('student')
        with self.assertRaises(RuleError):self.s.select(pid)
        with self.assertRaises(RuleError):self.s.wait(pid)
    def test_individual_approval_and_tasks(self):
        pid=self.project();self.login('student');aid=self.s.apply(pid,'My research proposal');self.assertIsNone(self.s.selected());self.login('teacher');self.s.review_application(aid,'Approved');self.login('student');self.assertEqual(self.s.selected(),pid);self.assertEqual(len(self.s.tasks()),5)
    def test_team_approval_atomic(self):
        pid=self.project(capacity=2);aid=self.team_application(pid);self.login('teacher');self.s.review_application(aid,'Approved');self.login('student');self.assertEqual(self.s.selected(),pid);self.login('mate');self.assertEqual(self.s.selected(),pid)
    def test_team_capacity_failure_changes_nothing(self):
        pid=self.project(capacity=2);aid=self.team_application(pid);self.login('admin');self.add('solo');self.login('solo');solo=self.s.apply(pid,'Independent research proposal');self.login('teacher');self.s.review_application(solo,'Approved')
        with self.assertRaises(RuleError):self.s.review_application(aid,'Approved')
        self.login('student');self.assertIsNone(self.s.selected());self.login('mate');self.assertIsNone(self.s.selected())
    def test_revision_and_resubmission(self):
        pid=self.project();self.login('student');aid=self.s.apply(pid,'First proposal');self.login('teacher');self.s.review_application(aid,'Changes requested','Add a clear evaluation plan.');self.login('student');self.s.resubmit(aid,'Revised proposal with evaluation plan');self.assertEqual(self.s.applications()[0]['status'],'Pending')
    def test_nonowner_cannot_review(self):
        self.add('advisor2','teacher');pid=self.project();self.login('student');aid=self.s.apply(pid,'Proposal');self.login('advisor2')
        with self.assertRaises(RuleError):self.s.review_application(aid,'Approved')
    def test_pending_blocks_team_change_and_direct_selection(self):
        pid=self.project();aid=self.team_application(pid)
        with self.assertRaises(RuleError):self.s.leave_team()
        with self.assertRaises(RuleError):self.s.select(1)
        self.s.withdraw(aid);self.login('mate');self.s.leave_team()
    def test_invitation_consent_and_private_inbox(self):
        self.add('mate');self.login('student');self.s.create_team('Team');self.s.invite('mate');self.assertEqual(len(self.s.team()['members']),1);self.assertEqual(self.s.invitations(),[]);self.login('mate');iid=self.s.invitations()[0]['id'];self.s.respond_invite(iid,False);self.assertIsNone(self.s.team())
    def test_milestones_scope_and_status(self):
        self.login('student');self.s.select(1);t=self.s.tasks()[0];self.s.update_task(t['id'],'Done');self.assertEqual(sum(x['status']=='Done' for x in self.s.tasks()),1);self.login('student2')
        with self.assertRaises(RuleError):self.s.update_task(t['id'],'Done')
    def test_custom_milestone_and_notification(self):
        self.login('teacher');self.s.add_task(1,'Evaluation plan',date.today().isoformat());self.login('student2');self.assertTrue(any(t['title']=='Evaluation plan' for t in self.s.tasks()));ns=self.s.notifications();self.assertTrue(any(n['title']=='Milestone due' for n in ns));count=len(ns);self.assertEqual(len(self.s.notifications()),count);self.s.read_notifications();self.assertTrue(all(n['is_read'] for n in self.s.notifications()))
    def test_submission_attachment_feedback_backup(self):
        self.login('student');self.s.select(1);source=self.dir/'report.txt';source.write_text('Prototype evaluation report.');self.s.submit('Proposal','https://example.com/repo','A note',str(source));source.unlink();sid=self.s.submissions()[0]['id'];self.assertEqual(self.s.attachment_path(sid).read_text(),'Prototype evaluation report.');self.login('teacher');self.s.review_submission(sid,'Changes requested','Add a comparison baseline.');self.login('student');self.assertEqual(self.s.submissions()[0]['feedback'],'Add a comparison baseline.');self.login('admin');backup=self.dir/'backup.zip';self.s.backup_bundle(backup)
        with zipfile.ZipFile(backup) as z:self.assertIn('workspace.db',z.namelist());self.assertTrue(any(n.startswith('attachments/') for n in z.namelist()))
    def test_submission_guards_and_scope(self):
        self.login('student');self.s.select(1)
        with self.assertRaises(RuleError):self.s.submit('Unsafe','javascript:alert(1)')
        source=self.dir/'bad.py';source.write_text('print(1)')
        with self.assertRaises(RuleError):self.s.submit('Unsafe',attachment=str(source))
        self.s.submit('Safe','https://example.com/repo');self.login('student3');self.assertEqual(self.s.submissions(),[])
    def test_preferences_survive_restart(self):
        self.s.save_preferences(dark=False,font_size=13,query='finance',width=1280,height=820);new=Service(self.dir/'workspace.db');new.login('admin','DemoPass123!');self.assertFalse(new.preferences()['dark']);self.assertEqual(new.preferences()['query'],'finance')
    def csv(self,name,text):p=self.dir/name;p.write_text(text);return p
    def test_csv_preview_is_readonly_and_import_atomic(self):
        p=self.csv('students.csv','id,name,major\nnew,New User,CS\nstudent,Duplicate,CS\n');before=len(self.s.accounts());preview=self.s.preview_import(p,'students','LongPass123!');self.assertEqual(len(self.s.accounts()),before)
        with self.assertRaises(RuleError):self.s.commit_import(preview)
        self.assertEqual(len(self.s.accounts()),before)
    def test_csv_quoted_commas_and_success(self):
        p=self.csv('projects.csv','title,supervisor,capacity\n"Research, Evaluation",Dr Test,3\n');preview=self.s.preview_import(p,'projects');self.s.commit_import(preview);self.assertTrue(any(p['title']=='Research, Evaluation' for p in self.s.projects()))
    def test_legacy_remaining_capacity_and_assignments(self):
        p=self.csv('legacy-projects.csv','project_id,project_name,remaining_team_members,supervisor_name\n99,Legacy topic,2,Dr Test\n');s=self.csv('legacy-students.csv','student_id,student_name,major,selected_project_id\n001,Example Student,CS,99\n');preview=self.s.preview_legacy(p,s,'LongPass123!',(date.today()+timedelta(days=20)).isoformat());self.s.commit_legacy(preview);pid=next(p['id'] for p in self.s.projects() if p['title']=='Legacy topic');self.assertEqual(next(p['capacity'] for p in self.s.projects() if p['id']==pid),3);self.s.login('001','LongPass123!');self.assertEqual(self.s.selected(),pid)
    def test_v2_database_migration(self):
        p=self.dir/'old.db';old=CoreService(p);old.login('student','DemoPass123!');old.select(2);new=Service(p);new.login('student','DemoPass123!');self.assertEqual(new.selected(),2);self.assertEqual(len(new.tasks()),5);self.assertTrue(all(p['selection_mode']=='Direct' for p in new.projects()))
    def test_closed_period_still_allows_waitlist_departure(self):
        pid=self.project(selection_mode='Direct',capacity=1);self.login('student');self.s.select(pid);self.login('student2');self.s.cancel();self.s.wait(pid);self.login('admin');self.s.save_settings(enabled='0');self.login('student2');self.s.wait(pid);self.assertFalse(next(p for p in self.s.projects() if p['id']==pid)['waiting'])
    def test_backup_cannot_overwrite_live_store(self):
        with self.assertRaises(RuleError):self.s.backup_bundle(self.dir/'workspace.db')
        self.assertTrue((self.dir/'workspace.db').read_bytes().startswith(b'SQLite'))
    def test_pdf_pagination_and_syntax(self):
        p=self.dir/'report.pdf';write_pdf(p,'Test report',['Long row '+str(i) for i in range(100)],'Demo User');data=p.read_bytes();self.assertTrue(data.startswith(b'%PDF-1.4'));self.assertIn(b'/Count 5',data);self.assertTrue(data.endswith(b'%%EOF\n'))

if __name__=='__main__':unittest.main()
