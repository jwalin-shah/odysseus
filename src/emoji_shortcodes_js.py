"""Generate JavaScript-compatible emoji shortcode data.

This module provides functionality to convert emoji shortcode mappings
into a JavaScript object literal format suitable for inclusion in
JavaScript applications.
"""


def emoji_shortcodes_js(shortcodes=None, indent=2):
    """Generate a JavaScript object string from emoji shortcodes.

    Args:
        shortcodes: Optional dictionary mapping shortcode names (without
                    colons) to emoji characters. If None, returns the
                    default set of emoji shortcodes.
        indent: Number of spaces for indentation in the output. Use 0
                for compact output. Defaults to 2.

    Returns:
        A string containing a JavaScript object literal that maps
        shortcode names to their corresponding emoji characters.

    Examples:
        >>> result = emoji_shortcodes_js()
        >>> "smile" in result
        True
        >>> result = emoji_shortcodes_js({"custom": "test"})
        >>> '"custom": "test"' in result
        True
    """
    if shortcodes is None:
        shortcodes = _default_shortcodes()
    elif not isinstance(shortcodes, dict):
        raise TypeError("shortcodes must be a dictionary")

    if not isinstance(indent, int) or indent < 0:
        raise ValueError("indent must be a non-negative integer")

    sorted_items = sorted(shortcodes.items(), key=lambda item: item[0])

    if indent == 0:
        pairs = []
        for key, value in sorted_items:
            escaped_key = _escape_js_string(key)
            escaped_value = _escape_js_string(value)
            pairs.append('"' + escaped_key + '": "' + escaped_value + '"')
        return "{" + ",".join(pairs) + "}"
    else:
        indent_str = " " * indent
        lines = ["{"]
        pair_strings = []
        for key, value in sorted_items:
            escaped_key = _escape_js_string(key)
            escaped_value = _escape_js_string(value)
            pair_strings.append(
                indent_str + '"' + escaped_key + '": "' + escaped_value + '"'
            )
        lines.append(",\n".join(pair_strings))
        lines.append("}")
        return "\n".join(lines)


def _escape_js_string(text):
    """Escape a string for use in a JavaScript string literal."""
    if not isinstance(text, str):
        text = str(text)
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    text = text.replace("\t", "\\t")
    return text


def _default_shortcodes():
    """Return the default dictionary of emoji shortcodes."""
    return {
        "100": "💯",
        "alien": "👽",
        "call_me": "🤙",
        "check_mark": "✔",
        "clap": "👏",
        "cloud": "☁",
        "crossed_fingers": "🤞",
        "eyes": "👀",
        "exclamation": "❗",
        "fire": "🔥",
        "fist": "✊",
        "ghost": "👻",
        "grin": "😀",
        "heart": "❤",
        "heart_eyes": "😍",
        "info": "ℹ",
        "joy": "😂",
        "moon": "🌙",
        "muscle": "💪",
        "ok_hand": "👌",
        "point_down": "👇",
        "point_left": "👈",
        "point_right": "👉",
        "point_up": "☝",
        "poop": "💩",
        "pray": "🙏",
        "question": "❓",
        "rain": "🌧",
        "raised_hands": "🙌",
        "robot": "🤖",
        "rocket": "🚀",
        "rofl": "🤣",
        "shrug": "🤷",
        "skull": "💀",
        "smile": "😄",
        "snow": "❄",
        "sparkles": "✨",
        "spock": "🖖",
        "star": "⭐",
        "sun": "☀",
        "tada": "🎉",
        "thinking": "🤔",
        "thumbs_down": "👎",
        "thumbs_up": "👍",
        "v": "✌",
        "warning": "⚠",
        "wave": "👋",
        "wink": "😉",
        "x": "❌",
        "zap": "⚡",
    }


if __name__ == "__main__":
    print(emoji_shortcodes_js())