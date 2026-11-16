import os

import uvicorn

from .app import create_app


def main() -> None:
    app = create_app(os.environ.get("DB_PATH", "crm.db"))
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8002")))


if __name__ == "__main__":
    main()
