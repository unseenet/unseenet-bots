# Bot profile pictures

Plain, original icons for the project's news bots, made by `make_icons.py` (Pillow):
128 px WebP without metadata, each with its alt text in `<bot>.alt`. They are not the
sources' logos on purpose - the UN emblem, CISA's seal and most organisations' logos may
not be used to stand for a channel that is not theirs - so each bot gets a symbol instead:
a globe for UN News (with a badge per topic), a megaphone, a magnifying glass, a leaf, a
shield, a bar chart, and a plain newspaper page for the headline channels.

In `bots.toml`: `picture = "~/.config/unseenet-bots/<bot>.webp"` and `picture_alt` in the
bot's `[bots.<name>.profile]`.
