"""PDF presentation only: render completed results without calculation or AI calls."""
from datetime import datetime, timedelta, timezone
from html import escape

from hand_technique import Prediction
from reading import ReadingSession
from utils.symbol_relations import describe_relation

VARIANTS = ('print', 'wechat')
DISCLAIMER = '本报告用于传统文化探索与思路梳理，不是确定性预测，也不作为医疗、法律或投资依据。现实决定请核实事实并咨询相应专业人士。'

CSS = '''
@page { size: A4; margin: 14mm 16mm 17mm;
  @bottom-left { content: "小六壬 · 传统文化探索"; font: 8pt sans-serif; color: #626968; }
  @bottom-right { content: counter(page) " / " counter(pages); font: 8pt sans-serif; color: #626968; }
}
* { box-sizing: border-box; }
html { background: white; color: #253836; font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans CJK SC", sans-serif; }
body { margin: 0; font-size: 10pt; line-height: 1.65; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
p { margin: 5pt 0; white-space: pre-wrap; overflow-wrap: anywhere; }
header { border-top: 3pt solid #8e493b; padding-top: 12pt; margin-bottom: 12pt; }
.topline { display: flex; justify-content: space-between; gap: 12pt; align-items: center; }
.brand { font-size: 11pt; letter-spacing: 2pt; font-weight: 600; }
.edition, .meta, .label { color: #626968; font-size: 8pt; }
h1 { font-family: "Songti SC", "SimSun", serif; font-size: 27pt; font-weight: 600; letter-spacing: 2pt; margin: 10pt 0 4pt; }
h2 { font-size: 12pt; margin: 12pt 0 6pt; padding-bottom: 4pt; border-bottom: 0.6pt solid #d9dfdb; color: #8e493b; break-after: avoid; }
h3 { font-size: 10pt; margin: 8pt 0 3pt; break-after: avoid; }
.question { font-size: 11pt; font-weight: 500; }
.summary { border-left: 2pt solid #8e493b; padding: 7pt 11pt; background: #f4f5f1; margin: 8pt 0; }
.summary p { margin: 0; }
ol { padding-left: 18pt; margin: 5pt 0; }
li { padding-left: 3pt; margin: 4pt 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.caution { border-top: 0.6pt solid #b19b81; border-bottom: 0.6pt solid #b19b81; padding: 5pt 0; margin: 10pt 0; }
.facts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10pt; }
.fact { padding: 8pt 0; }
.stage { color: #626968; font-size: 8pt; }
.symbol { font-family: "Songti SC", "SimSun", serif; font-size: 18pt; margin: 4pt 0; }
.element { font-size: 10pt; margin-left: 8pt; color: #626968; }
.fact p { font-size: 9pt; }
.relation { font-size: 9pt; margin: 5pt 0; }
.notice { margin-top: 12pt; border-top: 0.6pt solid #d9dfdb; padding-top: 7pt; font-size: 8pt; color: #626968; }
.continued { color: #626968; font-size: 9pt; }
.print { font-size: 9.5pt; line-height: 1.4; }
.print p { margin: 3pt 0; }
.print li { margin: 3pt 0; }
.print header { padding-top: 9pt; margin-bottom: 8pt; }
.print h1 { font-size: 25pt; margin-top: 8pt; }
.print h2 { margin-top: 8pt; margin-bottom: 4pt; font-size: 11pt; }
.print h3 { margin-top: 6pt; }
.print .summary { padding: 5pt 10pt; }
.print .notice { margin-top: 9pt; }
.wechat { font-size: 14pt; line-height: 1.75; }
.wechat header { padding-top: 10pt; margin-bottom: 16pt; }
.wechat h1 { font-size: 26pt; }
.wechat h2 { font-size: 17pt; margin-top: 18pt; }
.wechat h3 { font-size: 14pt; }
.wechat .brand { font-size: 12pt; }
.wechat .edition, .wechat .meta, .wechat .label, .wechat .stage { font-size: 10pt; }
.wechat .question { font-size: 15pt; }
.wechat .facts { display: block; }
.wechat .fact { border-bottom: 0.6pt solid #d9dfdb; break-inside: avoid; }
.wechat .symbol { font-size: 24pt; }
.wechat .element { font-size: 13pt; }
.wechat .fact p, .wechat .relation { font-size: 14pt; }
.wechat .local-facts { break-before: page; }
.wechat .notice, .wechat .continued { font-size: 11pt; }
.wechat p, .wechat li { orphans: 2; widows: 2; }
'''


def render_report(prediction: Prediction, *, variant: str, input_summary: str,
                  question: str, session: ReadingSession | None = None,
                  generated_at: datetime | None = None) -> str:
    """Return self-contained HTML. Print is an explicitly excerpted summary."""
    if variant not in VARIANTS:
        raise ValueError('未知报告版式')
    compact = variant == 'print'
    excerpted = False

    def text(value: str, limit: int = 0) -> str:
        nonlocal excerpted
        if compact:
            value = ' '.join(value.split())
        if compact and limit and len(value) > limit:
            value = value[:limit] + '…〔节选〕'
            excerpted = True
        return escape(value)

    def paragraph(value: str, limit: int = 0, css: str = '') -> str:
        return f'<p class="{css}">{text(value, limit)}</p>'

    now = generated_at or datetime.now(timezone(timedelta(hours=8)))
    stamp = now.astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M UTC+8')
    reading = session.reading if session else None
    edition = '打印版 · 单页摘要' if compact else '微信版 · 完整报告'
    state = ('AI 解读 · ' + (f'第 {len(session.supplements)} 次补充' if session.supplements else '初次解读')) if reading else '仅本地计算 · 未生成 AI 解读'
    content = [f'<header><div class="topline"><span class="brand">小六壬 / MINI SIX REN</span></div>',
               f'<h1>三传研读报告</h1><div class="edition">{edition}</div>',
               f'<p class="meta">生成于 {stamp}<br>项目九宫法 · {state}</p></header>',
               '<section><h2>本次所问</h2>', paragraph(question or '未填写问题，仅记录本地三传。', 100, 'question'),
               paragraph(input_summary, 100, 'meta')]
    if reading:
        content.extend(['<h2>核心判断 <span class="label">AI 象征解读</span></h2>',
                        '<div class="summary">', paragraph(reading.answer, 220), '</div>',
                        '<h3>下一步</h3><ol>'])
        content.extend(f'<li>{text(action, 80)}</li>' for action in reading.actions)
        content.append('</ol>')
        if reading.caution:
            content.extend(['<div class="caution"><h3>必要提醒</h3>', paragraph(reading.caution, 140), '</div>'])
    else:
        content.extend(['<div class="summary">', paragraph('本报告记录已完成的本地三传。未生成 AI 解读，不包含针对问题的判断或行动建议。'), '</div>'])
    if not compact:
        content.append(paragraph('下页起为三传事实与解释依据，可上下滑动继续阅读。', css='continued'))
    content.extend(['</section><section class="local-facts"><h2>三传依据 <span class="label">本地计算事实</span></h2>', '<div class="facts">'])
    for stage, symbol in zip(('初传 · 起点', '中传 · 过程', '末传 · 趋势'), prediction.symbols):
        content.extend([f'<div class="fact"><div class="stage">{stage}</div>',
                        f'<div class="symbol">{text(symbol.name)}<span class="element">{text(symbol.element.name)}</span></div>',
                        paragraph(symbol.description, 30), paragraph(symbol.interpretation, 55), '</div>'])
    content.append('</div>')
    for i, relation in enumerate(prediction.relations):
        content.append(paragraph(f'{("初传→中传", "中传→末传")[i]} · {relation} · ' +
                                 describe_relation(prediction.symbols[i], prediction.symbols[i + 1], relation), css='relation'))
    content.append(paragraph('三传表示观察阶段，不对应确定期限。关系以箭头左侧为主语，不能只凭生克判定吉凶。', css='meta'))
    if reading:
        content.extend(['<h3>象征解释 <span class="label">AI 解读依据</span></h3>', paragraph(reading.rationale, 120)])
        if not compact and reading.follow_up:
            content.extend(['<h3>可进一步思考</h3>', paragraph(reading.follow_up)])
    if session and session.supplements:
        if compact:
            content.append(paragraph(f'本次解读已结合 {len(session.supplements)} 次补充；补充原文请查看微信版。', css='meta'))
        else:
            content.append('<h2>已接纳的补充背景</h2>')
            for index, supplement in enumerate(session.supplements, 1):
                content.extend([f'<h3>补充 {index:02}</h3>', paragraph(supplement)])
    content.append('</section>')
    if compact:
        note = '部分内容标注〔节选〕。' if excerpted else ''
        content.append(paragraph(note + '此版为单页摘要；完整解读、追问提示与补充背景请导出微信版。', css='meta'))
    content.append(f'<footer class="notice">{DISCLAIMER}</footer>')
    page_css = '@page { size: 108mm 192mm; margin: 10mm 8mm 16mm; }' if not compact else ''
    return ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'none\'; base-uri \'none\'; form-action \'none\'">'
            f'<title>小六壬 · {edition}</title><style>{CSS}{page_css}</style></head>'
            f'<body class="{variant}"><article>{"".join(content)}</article></body></html>')
