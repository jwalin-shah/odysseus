"""Approval gate module: parses free-form CLI responses into normalized actions."""


def parse_confirmation_response(raw: str) -> str:
    """Normalize a free-form CLI reply into one of the canonical action tokens.

    Returns:
        'approve' - the user wants to proceed this time.
        'deny'    - the user wants to cancel/abort this time.
        'always'  - the user wants to proceed and remember for the future.
        'never'   - the user wants to never be asked again (or always cancel).
        'invalid' - the response did not match any known affirmative/negative pattern.
    """
    if not isinstance(raw, str):
        return 'invalid'
    text = raw.strip().lower()
    if not text:
        return 'invalid'

    approve_set = {
        'y', 'yes', 'yeah', 'yep', 'yup', 'sure', 'ok', 'okay', 'k',
        'approve', 'approved', 'confirm', 'confirmed', 'affirm',
        'agreed', 'agree', 'accept', 'accepted', 'go', 'proceed',
        'go ahead', 'do it', 'do', 'true', 'correct', 'right',
        'positive', 'aye', 'yea', 'definitely', 'certainly',
        'absolutely', 'indeed', 'of course', 'fine', 'alright',
        'aight', 'ye', 'ya', 'yah', 'yeh', 'yessir', 'roger',
        '10-4', 'affirmative', 'sounds good', 'perfect', 'great',
        'good', 'yas', 'righto', 'okey', 'okey-dokey', 'okey dokey',
    }

    deny_set = {
        'n', 'no', 'nope', 'nah', 'na', 'naw', 'nay', 'no way',
        'deny', 'denied', 'reject', 'rejected', 'refuse', 'refused',
        'negative', 'disagree', 'decline', 'declined', 'no thanks',
        'no thank you', 'wrong', 'incorrect', 'false', 'negatory',
        'absolutely not', 'definitely not', 'certainly not',
        "i can't", "i won't", 'i refuse', 'no can do', 'sorry no',
        'nein', 'non', 'niet', 'no sir',
    }

    always_set = {
        'always', 'all', 'every time', 'everytime', 'every',
        'forever', 'evermore', 'ever', 'eternally', 'permanently',
        'all the time', 'for good', 'for keeps', 'for life',
        'for ever', 'each time', 'each', 'at all times',
    }

    never_set = {
        'never', 'none', 'not at all', 'not ever', 'not once',
        'no way ever', 'no chance', 'fat chance', 'when pigs fly',
        'when hell freezes over', 'no siree', 'no sirree',
        'over my dead body', 'not on your life',
        'not in a million years', 'never ever',
    }

    if text in approve_set:
        return 'approve'
    if text in deny_set:
        return 'deny'
    if text in always_set:
        return 'always'
    if text in never_set:
        return 'never'
    return 'invalid'
