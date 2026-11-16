import os

import uvicorn

from .app import create_app
from .settings import Settings


def main() -> None:
    uvicorn.run(create_app(Settings()), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
