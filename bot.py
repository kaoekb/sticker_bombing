from sticker_bombing.app import StickerBombingApp
from sticker_bombing.config import load_settings
from sticker_bombing.content import PhraseBook
from sticker_bombing.store import SubscriptionStore


def main() -> None:
    settings = load_settings()
    phrase_book = PhraseBook.from_yaml("memes.yaml")
    store = SubscriptionStore(settings.bot.storage_path)
    app = StickerBombingApp(settings=settings, phrase_book=phrase_book, store=store)
    app.run()


if __name__ == "__main__":
    main()
