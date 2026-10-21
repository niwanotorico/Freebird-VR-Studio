# SPDX-License-Identifier: GPL-2.0-or-later
"""Controller look: Normal / See-through. LOCAL (only this headset, never synced).

Freebird draws each controller as a flat card (an Image node with controller_left/right.png,
ids #controller_main_bg / #controller_alt_bg, in freebird/ui/controller_panels.py), and every
bl_xr node writes depth even where the PNG is transparent. See-through makes the card faint and
draws it without the depth test, so the grab sphere and whatever is behind the card stay visible.
The buttons / icons on the card are separate nodes and keep their normal look.

This is the ONLY place VR Studio touches those card nodes. Freebird's files are never edited;
if the nodes are not found, nothing happens and the controllers stay as Freebird draws them.
Freebird's left/right-hand switch swaps the textures between the two cards, not the nodes,
so the style set here stays on both cards.
"""

CARD_IDS = ("controller_main_bg", "controller_alt_bg")
SEE_THROUGH_STYLE = {"opacity": 0.2, "depth_test": False}
SETTING_KEY = "controller_see_through"

_MISSING = object()
_saved = {}  # node id -> {style key: inline value before see-through (or _MISSING)}
_see_through = None


def _cards():
    try:
        from bl_xr import root
    except Exception:
        return []
    out = []
    for node_id in CARD_IDS:
        try:
            node = root.q(f"#{node_id}")
        except Exception:
            node = None
        if node is not None and isinstance(getattr(node, "style", None), dict):
            out.append((node_id, node))
    return out


def get_see_through():
    global _see_through
    if _see_through is None:
        from .grab import load_setting

        _see_through = load_setting(SETTING_KEY, False) is True
    return _see_through


def set_see_through(state, save=True):
    global _see_through
    _see_through = bool(state)
    if save:
        from .grab import save_setting

        save_setting(SETTING_KEY, _see_through)
    return apply()


def apply():
    """Put the cards in the current look. Returns how many cards were found (0 = untouched)."""
    cards = _cards()
    on = get_see_through()
    for node_id, node in cards:
        if on:
            if node_id not in _saved:
                _saved[node_id] = {k: node.style.get(k, _MISSING) for k in SEE_THROUGH_STYLE}
            node.style.update(SEE_THROUGH_STYLE)
        else:
            _restore(node_id, node)
    return len(cards)


def restore():
    """Back to Freebird's own look (plugin unregister); the saved setting is kept."""
    for node_id, node in _cards():
        _restore(node_id, node)


def _restore(node_id, node):
    saved = _saved.pop(node_id, None)
    if saved is None:
        return
    for key, value in saved.items():
        if value is _MISSING:
            node.style.pop(key, None)
        else:
            node.style[key] = value
