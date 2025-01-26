import copy
import html
import json
import logging
import traceback
from typing import Any, cast

import telegram
from telegram import Chat, Update
from telegram.ext import ContextTypes

from src.telegram_interface.helpers import send_to_dev_message
from src.telegram_interface.user_data import UserDataDataclass

logger = logging.getLogger(__name__)


class SkipMedicoverClientEncoder(json.JSONEncoder):
    def default(self, obj: UserDataDataclass) -> Any:
        obj_copy = copy.deepcopy(obj)
        obj_copy["medicover_client"] = None
        return super().default(obj_copy)


async def default_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception was raised:", exc_info=context.error)

    error = cast(Exception, context.error)

    if isinstance(error, telegram.error.NetworkError):
        logger.exception("Telegram network error. Skipping further error handling.")
        return

    tb_list = traceback.format_exception(None, error, error.__traceback__)
    tb_string = "".join(tb_list)

    if context.user_data is None:
        pretty_user_data = "null"
    else:
        pretty_user_data = json.dumps(context.user_data, indent=4, cls=SkipMedicoverClientEncoder)

    base_message = (
        "{base_error_message}\n"
        f"<pre>context.user_data = {html.escape(pretty_user_data)}</pre>\n\n"
        f"<pre>{html.escape(tb_string)}</pre>"
    )

    if update is None:
        base_error_message = "An exception was raised while handling an update"
        message = base_message.format(base_error_message=base_error_message)

        await send_to_dev_message(context, message)
        return

    if isinstance(error, KeyError):
        missing_key = error.args[0]
        if missing_key == "language":
            update = cast(Update, update)
            chat = cast(Chat, update.effective_chat)
            chat_id = chat.id

            logger.warning("KeyError: Missing 'language' key in user data.")
            await context.bot.send_message(
                chat_id=chat_id,
                text="The bot has not been initialized properly. Please run the /start command.",
            )
            return None
        else:
            base_error_message = f"KeyError: An error has occurred. Missing '{missing_key}' key in user data."
            message = base_message.format(base_error_message=base_error_message)

            await send_to_dev_message(context, message)
            logger.error("KeyError: An error has occurred. Missing '%s' key in user data.", missing_key)

    base_error_message = "An error has occurred."
    message = base_message.format(base_error_message=base_error_message)

    await send_to_dev_message(context, message)
