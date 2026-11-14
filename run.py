from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from paint.config import APP_NAME, APP_VERSION, load_settings

_settings = load_settings()
for _key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_key, str(_settings.threads))


def main() -> int:
    if "--version" in sys.argv:
        print(f"{APP_NAME} {APP_VERSION}")
        return 0
    if "--hardware" in sys.argv:
        from paint.hardware import main as hardware_main

        index = sys.argv.index("--hardware")
        return hardware_main(sys.argv[index + 1:])
    from paint.app import main as app_main

    return app_main()


if __name__ == "__main__":
    sys.exit(main())
