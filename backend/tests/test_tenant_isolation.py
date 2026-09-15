from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Base as CoreBase, Notification, WorkflowInstance
import domain_models as D
from domain_api import list_students
from main import dashboard


def _session():
    engine = create_engine('sqlite:///:memory:')
    CoreBase.metadata.create_all(bind=engine)
    D.Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session()


def test_student_list_fails_closed_across_tenant_boundaries():
    s = _session()
    s.add_all([
        D.Student(id='s_a', tenant_id='tenant_a', roll_no='A001', name='Alpha', dept_id='dept_1', program_id='prog_1', batch='2025', semester=1, status='active', cgpa=8.4),
        D.Student(id='s_b', tenant_id='tenant_b', roll_no='B001', name='Bravo', dept_id='dept_2', program_id='prog_2', batch='2025', semester=1, status='active', cgpa=7.2),
    ])
    s.commit()

    data = list_students(q='', dept='', program='', academic_year='', study_year=0, semester=0, section='', risk='', page=1, page_size=25, ctx={'tenant_id': 'tenant_a', 'office_n': 10, 'sub': 'u1', 'scope_level': 'campus', 'scope_ref': 'scope_global'}, s=s)
    ids = {row['id'] for row in data['students']}
    assert ids == {'s_a'}


def test_dashboard_counts_are_tenant_scoped():
    s = _session()
    s.add_all([
        WorkflowInstance(id='wf_a', tenant_id='tenant_a', office_n=4, state='submitted', initiator_id='u_a', title='Alpha workflow'),
        WorkflowInstance(id='wf_b', tenant_id='tenant_b', office_n=4, state='submitted', initiator_id='u_b', title='Bravo workflow'),
        Notification(id='n_a', tenant_id='tenant_a', user_id='u_a', title='Alpha alert', body='Alpha body', read=False),
        Notification(id='n_b', tenant_id='tenant_b', user_id='u_b', title='Bravo alert', body='Bravo body', read=False),
    ])
    s.commit()

    data = dashboard(ctx={'tenant_id': 'tenant_a', 'office_n': 4, 'sub': 'u_a'}, s=s)
    assert data['kpis']['inbox'] == 1
    assert data['kpis']['unread'] == 1
