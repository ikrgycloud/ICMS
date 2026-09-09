import os
import sys
import importlib.util

backend_dir = r'c:\Users\etaka\Music\ICMS\backend'
os.chdir(backend_dir)
sys.path.insert(0, backend_dir)


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


database = load('database', os.path.join(backend_dir, 'database.py'))
models = load('models', os.path.join(backend_dir, 'models.py'))
domain_models = load('domain_models', os.path.join(backend_dir, 'domain_models.py'))
authority = load('authority', os.path.join(backend_dir, 'authority.py'))
matrices = load('matrices', os.path.join(backend_dir, 'matrices.py'))
main = load('main', os.path.join(backend_dir, 'main.py'))

s = database.SessionLocal()
try:
    rows = s.query(models.User).filter(models.User.username.in_(['student', '25ECE072', '25ece072', 'aarav_kulkarni', 'professor'])).all()
    print('rows', [(u.username, u.password_hash, u.office_n, u.role, u.status) for u in rows])
    result = main.login(main.LoginIn(username='student', password='demo123'), s=s)
    print('student_login', result['user']['username'], result['token'][:30])
finally:
    s.close()
