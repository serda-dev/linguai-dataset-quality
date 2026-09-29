import os
import time

from .db import Store


def main():
    store = Store(os.environ["DATABASE_URL"])
    for _ in range(30):
        try:
            store.initialize()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("database initialization failed")


if __name__ == "__main__":
    main()
