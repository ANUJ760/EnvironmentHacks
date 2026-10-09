import json
from pathlib import Path
from ecotwin.api.main import app
Path('backend').mkdir(exist_ok=True)
Path('backend/openapi.json').write_text(json.dumps(app.openapi(),indent=2,sort_keys=True)+'\n')
