"""Configuration loader module.

Provides access to the built-in default configuration, which serves as
the lowest-priority layer in the configuration loading pipeline.
"""


def load_defaults() -> dict:
    """Return the built-in default configuration dictionary.

    This dictionary represents the lowest-priority layer of configuration.
    Values here are used when no other configuration source (e.g., file
    or environment variable) provides an override.

    Returns:
        dict: The default configuration with the following structure:
            {
                'port': int,
                'debug': bool,
                'db': {
                    'host': str,
                    'port': int,
                },
            }
    """
    return {
        'port': 8080,
        'debug': False,
        'db': {
            'host': 'localhost',
            'port': 5432,
        },
    }
