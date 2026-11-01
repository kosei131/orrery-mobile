"""Experimental single-candidate chronology coordinator. No feed or execution.
Caller supplies closed-bar evidence from the correct symbol/timeframe.
"""
from dataclasses import dataclass, field
from math import isfinite


def number(x):
    return type(x) in (int,float) and isfinite(x)


@dataclass
class Candidate:
    symbol: str
    side: str
    created_at: float
    expires_at: float
    context_at: float
    context_direction: str
    sweep_extreme: float
    sl_buffer: float
    state: str = field(default='WATCH', init=False)
    last_at: float = field(default=float('-inf'), init=False)
    poi: tuple | None = field(default=None, init=False)
    audit: list = field(default_factory=list, init=False)

    def __post_init__(self):
        if self.symbol not in ('XAUUSD','USDJPY') or self.side not in ('BUY','SELL'):
            raise ValueError('Unsupported symbol/side')
        if any(not number(x) for x in (self.created_at,self.expires_at,self.context_at,self.sweep_extreme,self.sl_buffer)):
            raise ValueError('Invalid numbers')
        if not self.context_at <= self.created_at < self.expires_at or self.sweep_extreme<=0 or self.sl_buffer<=0:
            raise ValueError('Invalid chronology/stop')
        if self.context_direction != ('UP' if self.side=='BUY' else 'DOWN'):
            raise ValueError('Directional context required; zone override not implemented')

    def step(self, *, symbol, timeframe, closed_at, bar, evidence=None):
        """One call per subsequent closed event; strictly increasing UTC times.
        evidence booleans are not inferred from price. No READY authorization.
        """
        evidence = evidence or {}
        if symbol != self.symbol or timeframe not in ('15m','5m') or not number(closed_at):
            raise ValueError('Wrong stream')
        if closed_at <= self.last_at or closed_at <= self.created_at:
            raise ValueError('Duplicate or unordered event')
        if any(not number(bar.get(k)) for k in ('open','high','low','close')) or not 0 < bar['low'] <= min(bar['open'],bar['close']) <= max(bar['open'],bar['close']) <= bar['high']:
            raise ValueError('Invalid closed OHLC')
        self.last_at=closed_at
        old=self.state
        if self.state=='INVALID':
            return self.state
        stop=self.sweep_extreme-self.sl_buffer if self.side=='BUY' else self.sweep_extreme+self.sl_buffer
        hit=bar['low']<=stop if self.side=='BUY' else bar['high']>=stop
        if closed_at>=self.expires_at or hit or evidence.get('data_ok') is not True or evidence.get('context_valid') is not True or evidence.get('news_clear') is not True or evidence.get('spread_ok') is not True:
            self.state='INVALID'
        elif self.state=='WATCH' and timeframe=='15m' and evidence.get('sweep_closed') is True:
            self.state='SWEEP'
        elif self.state=='SWEEP' and timeframe=='5m' and evidence.get('structure_closed') is True:
            poi=evidence.get('poi')
            if isinstance(poi,(tuple,list)) and len(poi)==2 and all(number(x) for x in poi) and 0<poi[0]<poi[1]:
                self.poi=tuple(poi);self.state='CONFIRM'
        elif self.state=='CONFIRM' and timeframe=='5m' and self.poi:
            if bar['low']<=self.poi[1] and bar['high']>=self.poi[0]:
                self.state='RETEST'
        elif self.state=='RETEST' and timeframe=='5m':
            # Require a separate subsequent closing confirmation, never same-bar fill.
            rejection=bar['close']>self.poi[1] if self.side=='BUY' else bar['close']<self.poi[0]
            if rejection and evidence.get('risk_checked') is True:
                self.state='READY'
        elif self.state=='READY' and evidence.get('risk_checked') is not True:
            self.state='INVALID'
        self.audit.append(dict(at=closed_at,timeframe=timeframe,before=old,after=self.state))
        return self.state
