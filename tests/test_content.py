import tempfile
import unittest
from pathlib import Path

from sticker_bombing.content import PhraseBook


class PhraseBookTests(unittest.TestCase):
    def test_loads_and_filters_empty_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "memes.yaml"
            path.write_text(
                "\n".join(
                    [
                        "memes:",
                        "  - one",
                        "  - ''",
                        "  - two",
                        "modes:",
                        "  coach:",
                        "    title: Coach",
                        "    description: Pushes harder",
                        "    phrases:",
                        "      - go",
                        "triggers:",
                        "  office:",
                        "    keywords:",
                        "      - дейли",
                        "    phrases:",
                        "      - standup survived",
                    ]
                ),
                encoding="utf-8",
            )

            phrase_book = PhraseBook.from_yaml(str(path))

            self.assertEqual(len(phrase_book), 2)
            self.assertIn(phrase_book.random_phrase(), {"one", "two"})
            self.assertTrue(phrase_book.has_mode("coach"))
            self.assertEqual(phrase_book.trigger_phrase("очередной дейли"), "standup survived")



if __name__ == "__main__":
    unittest.main()
