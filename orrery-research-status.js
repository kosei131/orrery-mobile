'use strict';
(() => {
  const $ = id => document.getElementById(id);
  let key = '', busy = false, generation = 0;
  function clear() { $('result').replaceChildren(); $('timing').textContent = ''; }
  function lock() {
    generation++; key = ''; $('key').value = ''; clear();
    $('state').textContent = '未認証'; $('refresh').disabled = true; $('logout').disabled = true;
  }
  const money = v => typeof v === 'number' && Number.isFinite(v)
    ? new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(v) : '不明';
  const number = v => typeof v === 'number' && Number.isFinite(v) ? v.toFixed(3) : '不明';
  function row(list, label, value) {
    const dt = document.createElement('dt'), dd = document.createElement('dd');
    dt.textContent = label; dd.textContent = String(value); list.append(dt, dd);
  }
  function render(j) {
    clear();
    if (j.audit_status !== 'CONSISTENT_RESEARCH_ARTIFACTS' || !j.accounts) {
      $('state').textContent = '監査停止：損益は表示できません'; return;
    }
    $('state').textContent = '保存結果の整合性を確認（稼働状況は不明）';
    $('timing').textContent = `対象期間 UTC：${j.period_start_utc} → ${j.period_end_utc} ｜ 閲覧開始時の監査 UTC：${j.snapshot_audited_at_utc}`;
    for (const mode of ['CONFIRMATION', 'RETEST']) {
      const a = j.accounts[mode]; if (!a) throw Error('INVALID');
      const section = document.createElement('section'), title = document.createElement('h2'), list = document.createElement('dl');
      title.textContent = mode === 'CONFIRMATION' ? '確認直後の候補 · 独立$3,000口座' : 'リテスト待ち · 独立$3,000口座';
      row(list, '確定取引の純損益', money(a.closed_trade_net_usd));
      row(list, '評価額の変化（未決済を含む）', money(a.equity_change_usd));
      row(list, '最大DD（観測時点）', money(a.max_sampled_equity_drawdown_usd));
      row(list, '確定取引数', a.closed_trades);
      row(list, '勝率（確定取引）', a.win_rate_fraction === null ? '不明' : `${(a.win_rate_fraction * 100).toFixed(1)}%`);
      row(list, '平均R / PF', `${number(a.expectancy_r)} / ${number(a.profit_factor)}`);
      row(list, '未決済件数', a.open_positions);
      row(list, '最大連敗', a.max_consecutive_losses);
      row(list, '日次停止 / 連敗停止', `${a.daily_stop_held ? 'あり':'なし'} / ${a.streak_stop_held ? 'あり':'なし'}`);
      section.append(title, list); $('result').append(section);
    }
  }
  async function request(path, token) {
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(path, {headers:{Authorization:`Bearer ${token}`}, cache:'no-store', signal:controller.signal});
      if (!response.ok) throw Error('UNAVAILABLE');
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  async function refresh() {
    if (busy || !key) return;
    busy = true; const current = ++generation, token = key;
    clear(); $('state').textContent = '保存結果を確認中…'; $('refresh').disabled = true;
    try {
      const index = await request('/api/runs', token);
      if (!index.runs || index.runs.length !== 1 || !/^[0-9a-f-]{36}$/.test(index.runs[0].run_id)) throw Error('INVALID');
      const data = await request(`/api/runs/${index.runs[0].run_id}/summary`, token);
      if (current !== generation) return;
      render(data); $('logout').disabled = false;
    } catch (_) {
      if (current !== generation) return;
      clear(); key = ''; $('state').textContent = '接続・認証失敗：現在状態は不明です。鍵を入力して再確認してください。';
      $('logout').disabled = true;
    } finally {
      busy = false; $('refresh').disabled = !key;
    }
  }
  $('unlock').onclick = () => {
    if (busy) return;
    key = $('key').value.trim(); $('key').value = '';
    if (!/^[A-Za-z0-9_-]{43}$/.test(key)) { lock(); $('state').textContent = '専用閲覧鍵を入力してください'; return; }
    refresh();
  };
  $('refresh').onclick = refresh; $('logout').onclick = lock;
})();
