"""Continuous-window quote coverage guard for the offline USD replay."""
from lsr03_account_replay import replay_account


class CoverageGap(Exception):
    def __init__(self, start_msc, end_msc, edge):
        self.start_msc = start_msc
        self.end_msc = end_msc
        self.edge = edge


def replay_continuous_window(quotes, candidates, *, start_msc, end_msc,
                             max_gap_msc, **account_inputs):
    """Apply a declared observation limit to a single half-open window.

    The caller chooses a continuous window. Scheduled closures need separate
    evidence and cannot be bridged here. The limit is an observation test,
    not proof that every broker tick was captured.
    """
    if (any(type(v) is not int for v in (start_msc, end_msc, max_gap_msc))
            or not 0 <= start_msc < end_msc or not 1 <= max_gap_msc <= 60000):
        raise ValueError('Explicit UTC window and 1–60000ms gap limit required')
    if account_inputs.pop('daily_boundary_utc_hour', 10) != 10:
        raise ValueError('Research day boundary must be 10:00 UTC')
    if not isinstance(candidates, list) or any(
            not isinstance(p, dict) or type(p.get('known_at_msc')) is not int
            or not start_msc <= p['known_at_msc'] < end_msc for p in candidates):
        raise ValueError('Candidates must originate within the declared window')

    def checked_quotes():
        previous = start_msc
        observed = False
        for quote in quotes:
            clock = quote.get('time_msc') if isinstance(quote, dict) else None
            if type(clock) is not int or not previous <= clock < end_msc:
                raise ValueError('Ordered quote inside the declared window required')
            if clock - previous > max_gap_msc:
                raise CoverageGap(previous, clock, 'INTERIOR' if observed else 'START')
            previous = clock
            observed = True
            yield quote
        if not observed:
            raise CoverageGap(start_msc, end_msc, 'EMPTY')
        if end_msc - previous > max_gap_msc:
            raise CoverageGap(previous, end_msc, 'END')

    coverage = dict(start_msc=start_msc, end_msc=end_msc, max_gap_msc=max_gap_msc,
                    broker_completeness_verified=False)
    try:
        account = replay_account(checked_quotes(), candidates,
                                 daily_boundary_utc_hour=10, **account_inputs)
    except CoverageGap as gap:
        return dict(status='BLOCKED_OBSERVATION_GAP', coverage=coverage, account=None,
                    gap=dict(start_msc=gap.start_msc, end_msc=gap.end_msc, edge=gap.edge),
                    execution_allowed=False)
    return dict(status='OBSERVED_WINDOW_RESEARCH_REPLAY', coverage=coverage,
                account=account, gap=None, execution_allowed=False)
