import time

from .db import Store
from .settings import Settings


def main():
    store = Store(Settings.from_env().database_url)
    for _ in range(30):
        try:
            store.initialize()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("database initialization failed")


if __name__ == "__main__":
    main()
