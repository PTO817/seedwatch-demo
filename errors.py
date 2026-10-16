"""Translate known infrastructure failures without mistaking them for retailer blocks."""
def collector_problem(log):
    lower=log.lower()
    if ('bootstrap_check_in' in lower and 'permission denied' in lower) or ('crashpad/settings.dat' in lower and 'operation not permitted' in lower):
        return ('Browser startup blocked by the local execution environment before the retailer loaded. '
                'Open Seedwatch from the normal Mac launcher and retry. No macOS security settings need to be disabled.')
    if 'executable doesn\'t exist' in lower or 'please run the following command to download new browsers' in lower:
        return 'The collector browser is not installed for this Python environment. Complete the Playwright browser installation in START_HERE.md.'
    return None
