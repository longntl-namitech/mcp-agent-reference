import os

from .server import create_gateway


def main() -> None:
    gateway = create_gateway(
        os.environ.get("API_BASE_URL", "http://localhost:8000"),
        os.environ["GATEWAY_SECRET"],
    )
    gateway.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "8001")))


if __name__ == "__main__":
    main()
