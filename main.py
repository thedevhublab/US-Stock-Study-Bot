import logging
from studybot.config import Settings
from studybot.db import Database
from studybot.discord_app import StudyBot, register_commands
from studybot.scheduler import create_scheduler


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    db = Database(settings.database_path)
    bot = StudyBot(settings, db)
    register_commands(bot)
    scheduler = create_scheduler(bot)

    original_setup = bot.setup_hook
    async def setup():
        await original_setup()
        scheduler.start()
    bot.setup_hook = setup
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
