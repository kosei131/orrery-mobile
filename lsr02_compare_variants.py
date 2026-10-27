"""Reproducible illustrative comparison; synthetic candles, NOT broker data."""
import json
from lsr02_seeded_replay import simulate

def run():
    variants=[("BASE",False,False),("ADX",True,False),
              ("ATR",False,True),("ADX_ATR",True,True)]
    rows=[]
    for name,adx,atr in variants:
        r=simulate(seed=260427,steps=1500,use_adx=adx,use_atr_stop=atr)
        rows.append(dict(variant=name,trades=r["trades"],wins=r["wins"],
                         win_rate=r["win_rate"],net_pnl_usd=r["net_pnl_usd"],
                         sampled_max_drawdown_usd=r["sampled_max_drawdown_usd"],
                         price_hash=r["price_series_sha256"]))
    assert len(set(row["price_hash"] for row in rows))==1
    return rows

if __name__=="__main__":
    print("ORRERY_SYNTHETIC_VARIANTS="+json.dumps(run(),sort_keys=True))
