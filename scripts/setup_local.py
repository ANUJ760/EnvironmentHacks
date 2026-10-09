"""Safe onboarding: generate a local secret without printing or committing it."""
from pathlib import Path
import secrets
if not Path('.env').exists():
    document=Path('.env.example').read_text().replace('DEV_JWT_SECRET=','DEV_JWT_SECRET='+secrets.token_hex(32),1)
    Path('.env').write_text(document)
    Path('.env').chmod(0o600)
print('Local .env is ready. Keep it untracked; download datasets using docs/DATASETS.md.')
