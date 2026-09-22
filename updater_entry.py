"""Standalone Windows helper so the running application can be replaced."""
from core.update_install import main

if __name__ == '__main__':
    raise SystemExit(main())
