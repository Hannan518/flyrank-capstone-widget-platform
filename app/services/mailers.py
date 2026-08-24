import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class Mailer(Protocol):
    name: str

    async def send_confirmation(self, to_email: str, widget_title: str) -> None: ...


class ConsoleMailer:
    name = "console"

    async def send_confirmation(self, to_email: str, widget_title: str) -> None:
        logger.info(
            "[fake email] To: %s | Subject: Thanks for signing up via %s | "
            "Body: Your submission was received.",
            to_email,
            widget_title,
        )


def build_mailer(mode: str) -> Mailer:
    if mode == "console":
        return ConsoleMailer()
    raise ValueError(f"unsupported EMAIL_MODE: {mode}")
