def parse(text):
    """
    Parse INI-style configuration text into a nested dictionary.

    Lines starting with ';' or '#' are treated as comments and ignored.
    Blank lines are ignored. Lines of the form '[section]' define a section.
    Lines of the form 'key = value' are key-value pairs. Keys appearing
    before any section are placed under a 'default' key. Repeated sections
    have their entries merged into the same dict.

    Args:
        text: The INI-style text to parse.

    Returns:
        A dict mapping section names to dicts of key-value pairs.
        Keys that appear before any section header are returned under
        the 'default' key (only included if such keys exist).
    """
    result = {}
    current_section = None

    for line in text.splitlines():
        stripped = line.strip()

        # Skip blank lines and comments
        if not stripped or stripped.startswith(';') or stripped.startswith('#'):
            continue

        # Section header: [section_name]
        if stripped.startswith('[') and stripped.endswith(']'):
            section_name = stripped[1:-1].strip()
            if section_name not in result:
                result[section_name] = {}
            current_section = section_name
            continue

        # Key-value pair: key = value
        if '=' in stripped:
            key, _, value = stripped.partition('=')
            key = key.strip()
            value = value.strip()

            if current_section is None:
                # Keys before any [section] go under 'default'.
                # Only create the 'default' bucket when we actually
                # have a key to put in it.
                result.setdefault('default', {})[key] = value
            else:
                result[current_section][key] = value

    return result