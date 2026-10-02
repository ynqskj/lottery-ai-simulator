"""Presentation-only workspaces; existing dashboard actions and data are reused."""
import html
import re

PAGES = (("overview", "总览"), ("generate", "生成推荐"), ("analysis", "号码分析"),
         ("history", "推荐历史"), ("reports", "报告"), ("settings", "大模型配置"))


def _flat(markup):
    markup = re.sub(r"<details([^>]*)>", r"<section\1>", markup)
    markup = markup.replace("</details>", "</section>")
    markup = re.sub(r"<summary([^>]*)>", r'<div class="section-heading">', markup).replace("</summary>", "</div>")
    markup = re.sub(r'<span class="history-toggle[^>]*>.*?</span>', '', markup)
    markup = re.sub(r'<strong class="batch-toggle-text">.*?</strong>', '', markup)
    return markup.replace("点开批次可查看", "每个批次直接展示")


def _generation_actions(games):
    from lottery_sim import dashboard as d
    actions = _flat(d._render_actions(games))
    actions = re.sub(r'<nav class="game-action-tabs".*?</nav>', '', actions, flags=re.S)
    actions = actions.replace('<h2>本地操作</h2>', '<h2>生成推荐</h2>')
    # Move the same action buttons ahead of each game's existing parameter controls.
    def move_buttons(match):
        opening, body = match.group(1), match.group(2)
        found = re.search(r'<div class="action-buttons">.*?</div>', body, re.S)
        return opening + found.group(0) + body.replace(found.group(0), '', 1) + '</div>'
    actions = re.sub(r'(<div class="game-action-pane[^>]*>)(.*?<div class="action-buttons">.*?</div>\s*)</div>', move_buttons, actions, flags=re.S)
    def parameter_tabs(match):
        markup = match.group(0)
        keys = [('basic', '基础设置')]
        markup = re.sub(r'<div class="basic-param-grid">(.*?)</div>', r'<div class="parameter-page active" data-param-panel="basic"><div class="basic-param-grid">\1</div></div>', markup, flags=re.S)
        def advanced(section):
            key = 'positions' if 'data-position-enable' in section.group(0) else 'training'
            keys.append((key, '位组合' if key == 'positions' else '训练参数'))
            return '<div class="parameter-page" data-param-panel="'+key+'">'+section.group(0)+'</div>'
        markup = re.sub(r'<section class="advanced-params">.*?</section>', advanced, markup, flags=re.S)
        tabs = '<nav class="parameter-tabs" aria-label="参数分组">' + ''.join(f'<button type="button" class="action-button{ " active" if key == "basic" else ""}" data-param-tab="{key}" aria-pressed="{ "true" if key == "basic" else "false"}">{label}</button>' for key,label in keys) + '</nav>'
        return markup.replace('<div class="parameter-page active"', tabs+'<div class="parameter-page active"', 1)
    actions = re.sub(r'<section class="param-panel">.*?\n</section>', parameter_tabs, actions, flags=re.S)
    return actions


def _summary_markup(game, summary_text):
    from lottery_sim import dashboard as d
    scoped = d._filter_summary_for_game(summary_text, game)
    headers, rows, notes = [], [], []
    for line in scoped.splitlines():
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|')]
            if all(re.fullmatch(r'[-: ]+', cell or '-') for cell in cells):
                continue
            if not headers:
                headers = cells
            else:
                rows.append(cells)
        elif line.startswith(('统计口径', '奖金口径')):
            notes.append(line)
    table = ''
    if rows:
        headings = ''.join('<th>'+html.escape(cell)+'</th>' for cell in headers)
        body = ''.join('<tr>'+''.join('<td>'+html.escape(cell)+'</td>' for cell in row)+'</tr>' for row in rows)
        table = '<table><thead><tr>'+headings+'</tr></thead><tbody>'+body+'</tbody></table>'
    elif scoped.strip() and not headers:
        table = '<div class="summary-text">'+''.join('<p>'+html.escape(line)+'</p>' for line in scoped.splitlines() if line.strip())+'</div>'
        notes = []
    else:
        table = '<p class="empty">暂无该彩种长期统计。</p>'
    notes_html = ''.join('<p class="panel-note">'+html.escape(note)+'</p>' for note in notes)
    return '<section class="panel"><h2>'+html.escape(game.name)+' 长期汇总</h2>'+table+notes_html+'</section>'


def _batch_reader(games):
    from lottery_sim import dashboard as d
    choices = []
    batches = []
    for index, batch in enumerate(d._recommendation_batches(games)):
        label = f'{batch.game_name} · {batch.target_issue} · {batch.generated_at} · {batch.count}注'
        choices.append(f'<option value="{index}" data-batch-game="{html.escape(batch.game_code)}">{html.escape(label)}</option>')
        markup = _flat(d._render_recommendation_batch(batch))
        batches.append('<div data-batch-panel="'+str(index)+'">'+markup+'</div>')
    return '<section class="panel"><label class="batch-picker-label">选择生成批次<select data-batch-picker>'+''.join(choices)+'</select></label><p data-batch-empty class="empty" hidden>当前彩种暂无生成批次。</p>'+''.join(batches)+'</section>'


def _report_reader(game):
    tabs, panels = [], []
    for index, (title, text) in enumerate(game.reports.items()):
        if not text:
            continue
        key = str(index)
        tabs.append(f'<button type="button" class="action-button" data-report-tab="{key}">{html.escape(title)}</button>')
        panels.append(f'<section data-report-panel="{key}"><h2>{html.escape(game.name)} {html.escape(title)}</h2><pre>{html.escape(text)}</pre></section>')
    return '<section class="panel report-reader"><nav class="report-reader-tabs" aria-label="报告类型">'+''.join(tabs)+'</nav>'+''.join(panels)+'</section>' if tabs else '<section class="panel"><p class="empty">暂无该彩种报告。</p></section>'


def render_workspace(model):
    from lottery_sim import dashboard as d
    nav = ''.join(f'<button type="button" class="workspace-nav-button{ " active" if index == 0 else ""}" data-workspace-nav="{key}" aria-current="{ "page" if index == 0 else "false"}">{label}</button>' for index, (key, label) in enumerate(PAGES))
    options = ''.join(f'<option value="{html.escape(game.code)}"{ " selected" if index == d._default_game_index(model.games) else ""}>{html.escape(game.name)}</option>' for index, game in enumerate(model.games))
    actions = _generation_actions(model.games)
    content = {
        'overview': ''.join(_game_section(game, d._render_game_overview(game)) for game in model.games),
        'generate': '<div class="generation-layout"><div>'+actions+'</div><div>'+''.join(_game_section(game, d._render_game_candidates(game)) for game in model.games)+'</div></div>',
        'analysis': ''.join(_game_section(game, d._render_game_analysis(game)) for game in model.games),
        'history': '<nav class="history-layout-tabs" aria-label="历史展示"><button type="button" class="action-button active" data-history-view="records" aria-pressed="true">全部记录</button><button type="button" class="action-button" data-history-view="summary" aria-pressed="false">长期汇总</button><button type="button" class="action-button" data-history-view="batches" aria-pressed="false">生成批次</button></nav><section class="history-layout-panel active" data-history-panel="records">' + ''.join(_game_section(game, '<section class="panel">'+d._render_recommendation_history_table(game)+'</section>') for game in model.games) + '</section><section class="history-layout-panel" data-history-panel="summary">' + ''.join(_game_section(game, _summary_markup(game, model.recommendation_summary)) for game in model.games) + '</section><section class="history-layout-panel" data-history-panel="batches">' + _batch_reader(model.games) + '</section>',
        'reports': ''.join(_game_section(game, _report_reader(game)) for game in model.games),
        'settings': _flat(d._render_backend_panel(model)),
    }
    pages = ''.join(f'<section class="workspace-page{ " active" if index == 0 else ""}" data-workspace-page="{key}" aria-label="{label}">{content[key]}</section>' for index, (key, label) in enumerate(PAGES))
    return f'<div class="workspace-layout"><aside class="workspace-sidebar"><p class="workspace-nav-title">工作区</p><nav aria-label="工作区导航">{nav}</nav></aside><div class="workspace-main"><div class="workspace-toolbar"><label for="workspace-game">当前彩种</label><select id="workspace-game">{options}</select><span id="workspace-title">总览</span></div>{pages}</div></div>'


def _game_section(game, markup):
    return f'<div data-workspace-game="{html.escape(game.code)}">{_flat(markup)}</div>'


def layout_css():
    return """
.workspace-layout { display: grid; grid-template-columns: 168px minmax(0, 1fr); gap: 20px; align-items: start; }
.workspace-sidebar { background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 12px; position: sticky; top: 16px; }
.workspace-nav-title { color: var(--muted); font-size: 13px; margin: 0 8px 10px; }
.workspace-sidebar nav { display: grid; gap: 6px; }
.workspace-nav-button { border: 0; background: transparent; color: var(--text); padding: 12px; text-align: left; cursor: pointer; border-radius: 8px; font: inherit; min-height: 44px; }
.workspace-nav-button.active { background: var(--surface-2); color: var(--blue); font-weight: 700; }
.workspace-nav-button:hover { background: var(--surface-2); }
.workspace-nav-button:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.workspace-main { min-width: 0; }
.workspace-toolbar { position: sticky; top: 0; z-index: 5; }
.generation-layout { display: grid; grid-template-columns: minmax(300px, 1fr) minmax(300px, 1fr); gap: 16px; align-items: start; }
.generation-layout > div { min-width: 0; }
.workspace-page .actions .action-buttons { margin: 10px 0 12px; position: sticky; top: 70px; z-index: 4; background: var(--surface); padding: 8px 0; }
.parameter-tabs, .report-reader-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin: 12px 0; }
.parameter-tabs .active, .report-reader-tabs .active { color: var(--blue); border-color: var(--blue); }
.parameter-page { display: none; }
.parameter-page.active { display: block; }
.report-reader pre { max-height: 60vh; overflow: auto; }
.report-reader [data-report-panel] { display: none; }
.report-reader [data-report-panel].active { display: block; }
.batch-picker-label { display: grid; gap: 8px; font-weight: 700; margin-bottom: 16px; }
[data-batch-panel][hidden] { display: none; }
@media (max-width: 1000px) { .generation-layout { grid-template-columns: 1fr; } }

.app-header p { overflow-wrap: anywhere; }
.history-layout-tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.history-layout-tabs .active { color: var(--blue); border-color: var(--blue); }
.history-layout-panel { display: none; }
.history-layout-panel.active { display: block; }
.workspace-toolbar { display: flex; align-items: center; gap: 12px; padding: 12px 14px; background: var(--surface); border: 1px solid var(--line); border-radius: 8px; margin-bottom: 16px; }
.workspace-toolbar label { font-weight: 700; white-space: nowrap; }
.workspace-toolbar select, .workspace-page select { border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; background: var(--surface); color: var(--text); font: inherit; }
#workspace-title { margin-left: auto; color: var(--muted); }
.workspace-page { display: none; }
.workspace-page.active { display: block; }
.workspace-page .view { display: block; }
.workspace-page .actions, .workspace-page .panel { margin-top: 0; margin-bottom: 16px; }
.workspace-page .advanced-params { padding: 14px; margin-top: 14px; }
.section-heading { font-weight: 700; margin-bottom: 12px; }
.workspace-page .recommendation-batch .section-heading { display: flex; flex-wrap: wrap; gap: 10px 20px; color: var(--muted); font-size: 13px; }
.workspace-page .recommendation-batch .section-heading span:first-child { color: var(--text); font-weight: 700; }
.workspace-page .recommendation-batch { margin-bottom: 16px; }
.workspace-page .backend-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.workspace-page .backend-card { min-width: 0; }
.workspace-page .backend-card input { box-sizing: border-box; }
.table-scroll { overflow-x: auto; max-width: 100%; }
.table-pagination { display: flex; gap: 10px; align-items: center; padding: 12px 0 0; flex-wrap: wrap; color: var(--muted); font-size: 13px; }
.table-pagination button { border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--text); padding: 7px 12px; cursor: pointer; font: inherit; }
.table-pagination button:disabled { opacity: .5; cursor: default; }
.workspace-page #action-details { margin-top: 16px; }
@media (max-width: 1000px) { .workspace-layout { grid-template-columns: 144px minmax(0,1fr); gap: 12px; } .workspace-page .backend-grid { grid-template-columns: 1fr; } }
@media (max-width: 760px) { .workspace-layout { grid-template-columns: 1fr; } .workspace-sidebar { position: static; } .workspace-sidebar nav { display: flex; flex-wrap: wrap; } .workspace-nav-title { display: none; } .workspace-nav-button { flex: 1 0 28%; text-align: center; padding: 8px; } .workspace-toolbar { flex-wrap: wrap; } .workspace-toolbar select { min-width: 0; } #workspace-title { font-size: 13px; } }
"""


def layout_js():
    return """
const workspaceGame = document.getElementById('workspace-game');
const workspaceNavigation = document.querySelectorAll('[data-workspace-nav]');
function updateBatchReader(game) {
  const picker = document.querySelector('[data-batch-picker]');
  const choices = Array.from(picker.options).filter(option => option.dataset.batchGame === game);
  Array.from(picker.options).forEach(option => { option.hidden = option.dataset.batchGame !== game; option.disabled = option.hidden; });
  if (!choices.some(option => option.value === picker.value)) picker.value = choices.length ? choices[0].value : '';
  picker.disabled = choices.length === 0;
  document.querySelector('[data-batch-empty]').hidden = choices.length !== 0;
  document.querySelectorAll('[data-batch-panel]').forEach(panel => { panel.hidden = !choices.length || panel.dataset.batchPanel !== picker.value; });
}
document.querySelector('[data-batch-picker]').addEventListener('change', () => updateBatchReader(workspaceGame.value));
document.querySelectorAll('[data-game-pane]').forEach(pane => {
  pane.querySelectorAll('[data-param-tab]').forEach(button => button.addEventListener('click', () => {
    pane.querySelectorAll('[data-param-tab]').forEach(item => { item.classList.toggle('active', item === button); item.setAttribute('aria-pressed', item === button ? 'true' : 'false'); });
    pane.querySelectorAll('[data-param-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.paramPanel === button.dataset.paramTab));
  }));
});
document.querySelectorAll('.report-reader').forEach(reader => {
  const tabs = Array.from(reader.querySelectorAll('[data-report-tab]'));
  const select = button => {
    tabs.forEach(item => { item.classList.toggle('active', item === button); item.setAttribute('aria-pressed', item === button ? 'true' : 'false'); });
    reader.querySelectorAll('[data-report-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.reportPanel === button.dataset.reportTab));
  };
  tabs.forEach(button => button.addEventListener('click', () => select(button)));
  if (tabs.length) select(tabs[0]);
});
function selectWorkspaceGame() {
  const game = workspaceGame.value;
  document.querySelectorAll('[data-workspace-game]').forEach(section => { section.hidden = section.dataset.workspaceGame !== game; });
  document.querySelectorAll('[data-game-pane]').forEach(pane => pane.classList.toggle('active', pane.dataset.gamePane === game));
  updateBatchReader(game);
}
document.querySelectorAll('[data-history-view]').forEach(button => button.addEventListener('click', () => {
  document.querySelectorAll('[data-history-view]').forEach(item => { item.classList.toggle('active', item === button); item.setAttribute('aria-pressed', item === button ? 'true' : 'false'); });
  document.querySelectorAll('[data-history-panel]').forEach(panel => panel.classList.toggle('active', panel.dataset.historyPanel === button.dataset.historyView));
}));
workspaceGame.addEventListener('change', selectWorkspaceGame);
selectWorkspaceGame();
workspaceNavigation.forEach(button => button.addEventListener('click', () => {
  const page = button.dataset.workspaceNav;
  workspaceNavigation.forEach(item => { const selected = item === button; item.classList.toggle('active', selected); item.setAttribute('aria-current', selected ? 'page' : 'false'); });
  document.querySelectorAll('[data-workspace-page]').forEach(section => section.classList.toggle('active', section.dataset.workspacePage === page));
  document.getElementById('workspace-title').textContent = button.textContent;
}));
document.querySelectorAll('.workspace-page table').forEach(table => {
  const wrapper = document.createElement('div'); wrapper.className = 'table-scroll';
  table.parentNode.insertBefore(wrapper, table); wrapper.appendChild(table);
  const rows = Array.from(table.querySelectorAll('tbody > tr'));
  const size = 5;
  if (rows.length <= size) return;
  const controls = document.createElement('div'); controls.className = 'table-pagination';
  const previous = document.createElement('button'); previous.type = 'button'; previous.textContent = '上一页';
  const label = document.createElement('span'); label.setAttribute('role', 'status'); label.setAttribute('aria-live','polite');
  const next = document.createElement('button'); next.type = 'button'; next.textContent = '下一页';
  let page = 0;
  const update = () => { rows.forEach((row, index) => { row.hidden = index < page * size || index >= (page + 1) * size; }); previous.disabled = page === 0; next.disabled = (page + 1) * size >= rows.length; label.textContent = `第 ${page + 1} / ${Math.ceil(rows.length / size)} 页，共 ${rows.length} 条`; };
  previous.addEventListener('click', () => { page--; update(); }); next.addEventListener('click', () => { page++; update(); });
  controls.append(previous, label, next); wrapper.after(controls); update();
});
"""
