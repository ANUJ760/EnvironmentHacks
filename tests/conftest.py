import os
os.environ.setdefault('APP_ENV','test')
os.environ.setdefault('DEV_JWT_SECRET','isolated-test-secret-only-32-characters-long')
os.environ.setdefault('DATABASE_URL','postgresql+psycopg://ecotwin:ecotwin_local_only@localhost:55432/ecotwin')
