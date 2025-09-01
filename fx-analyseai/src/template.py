def render(item, ccys, pairs, labels, senti, impact):
    bias = "強気" if senti>0 else "弱気" if senti<0 else "中立"
    lab = ", ".join(labels)
    return f"""【超要約（仮）】{item['title']}
- 種別: {lab} / 想定バイアス: {bias} / 重要度: {impact:.1f}
- 対象通貨: {', '.join(ccys) or '（特定不可）'} / 影響ペア: {', '.join(pairs) or '（推定なし）'}
- 概要: {item['summary'][:220]}...

【If-Then】
- もし市場が「{bias}」継続 → {('通貨買い寄り' if senti>0 else '通貨売り寄り' if senti<0 else 'レンジ/次材料待ち')}
- 逆転条件：初動と逆方向＋出来高増ならフェイク注意

出典: {item['source']} | リンク: {item['link']}
※投資助言ではありません。"""