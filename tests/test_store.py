import tempfile
import unittest
from pathlib import Path

from sticker_bombing.store import ChatState, SubscriptionStore


class SubscriptionStoreTests(unittest.TestCase):
    def test_persists_chat_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "subscriptions.json"
            store = SubscriptionStore(path)

            store.save_chat_states(
                {
                    2: ChatState(mode="classic", last_reply_at=10.0),
                    1: ChatState(mode="coach", last_reply_at=20.0),
                }
            )

            loaded = store.load_chat_states(default_mode="classic")
            self.assertEqual(set(loaded), {1, 2})
            self.assertEqual(loaded[1].mode, "coach")
            self.assertEqual(loaded[2].last_reply_at, 10.0)

    def test_migrates_legacy_chat_ids_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "subscriptions.json"
            path.write_text('{"chat_ids": [7, 9]}', encoding="utf-8")
            store = SubscriptionStore(path)

            loaded = store.load_chat_states(default_mode="classic")

            self.assertEqual(set(loaded), {7, 9})
            self.assertTrue(all(state.mode == "classic" for state in loaded.values()))


if __name__ == "__main__":
    unittest.main()
