# Claude Code への指示（日本語・厳密仕様）
あなたは **Google Apps Script（GAS）** と **Discord Webhook/Embed** に精通した上級エンジニアです。  
以下の要件を満たす **単一ファイル（`Code.gs`）** の実装と、最小限の導入手順・テスト手順を日本語コメント付きで出力してください。

## 目的
- Gmail の指定ラベル/検索条件に合致する **新着スレッドのみ** を、**Discord の #alerts** チャンネル（Webhook）に **Embed 形式** で自動共有する。
- 実行は **時間主導トリガー**（例：10分ごと）で定期実行。
- **重複防止**は Gmail の「処理済み」ラベル（任意名）で行う。

## 仕様（必須）
### 1) 設定値
コード先頭に **設定セクション** を用意し、以下を定数または Script Properties で管理できるようにする（Webhook は Script Properties 推奨）。
- `GMAIL_QUERY` : 既定例は `label:ToDiscord -in:chats newer_than:2d`  
  - Gmail 検索演算子をそのまま使うこと。  
  - `newer_than` は **日/週/月単位のみ**（分は不可）であることに留意する。  
- `PROCESSED_LABEL` : 既定例 `ToDiscord-処理済み`（存在しなければ自動作成）  
- `MAX_THREADS_PER_RUN` : 既定 30  
- `PREVIEW_MAX_CHARS` : 既定 180（本文プレビューの最大文字数、改行/空白整形）
- `TIMEZONE` : 既定 `Asia/Tokyo`
- `DISCORD_WEBHOOK_URL` : Script Properties から取得（`PropertiesService.getScriptProperties()` 利用）。  
  - `setWebhookUrl()` ユーティリティ関数を用意し、初期設定できるようにする。

### 2) 抽出ロジック
- 検索は `GMAIL_QUERY` に **`-label:"PROCESSED_LABEL"`** を付与して重複除外して実行。
- 対象は **スレッド単位**。取得上限は `MAX_THREADS_PER_RUN`。
- **新着スレッドだけ**を扱う前提なので、スレッド内の1通目（または最新）から以下情報を取り出す：  
  - 件名（`thread.getFirstMessageSubject()`）  
  - 差出人（`message.getFrom()`）  
  - 本文プレビュー（`message.getPlainBody()` をベースにHTML/引用/署名を軽く除去・整形し、`PREVIEW_MAX_CHARS`でトリム）  
  - メールへのリンク：`https://mail.google.com/mail/u/0/#inbox/{threadId}` を生成（スレッド全体でOK）
- 投稿が **成功したスレッド** にのみ `PROCESSED_LABEL` を付与する（失敗時は付けない）。

### 3) Discord Webhook 投稿（Embed形式）
- `UrlFetchApp.fetch` で JSON POST。`contentType: "application/json"`, `muteHttpExceptions: true`。
- 送信ボディ例（調整可、長すぎる場合はトリム）：
  ```json
  {
    "username": "Gmail Alerts",
    "embeds": [{
      "title": "メール件名",
      "url": "https://mail.google.com/mail/u/0/#inbox/THREAD_ID",
      "description": "本文プレビュー（PREVIEW_MAX_CHARS以内）",
      "fields": [
        {"name": "From", "value": "差出人", "inline": true},
        {"name": "Query", "value": "label:ToDiscord -in:chats newer_than:2d", "inline": true}
      ],
      "timestamp": "ISO8601",
      "footer": {"text": "GAS Gmail→Discord"}
    }]
  }
  ```
- **ステータスコード 204 または 200 を成功** と判定。  
- レート制限・一時失敗に備え、**簡易リトライ**（例：最大3回、指数バックオフ）と**軽いスロットリング**（例：`Utilities.sleep(200)`）を実装。

### 4) 重複防止
- 実行前検索で `-label:"PROCESSED_LABEL"` を付与。  
- 成功時に **スレッド** にラベル付与。  
- これにより **「指定ラベルの新着スレッドだけが1回ずつ配信」** を満たす。

### 5) ロギングと例外
- 失敗は `console.log` に要因・HTTPレスポンス・対象スレッドIDを記録。  
- 例外は握り潰さずにスレッド単位で継続処理（他のスレッドに影響させない）。

### 6) テスト用ユーティリティ
- `dryRun()`：実際には送らず、今回対象になるスレッド件数・件名・差出人・リンクをログ出力。  
- `testOne()`：ダミーEmbedを1件Webhookへ送信して接続確認。  
- `createTimeTrigger()`：10分間隔の時間主導トリガーを作成。  
- `deleteTriggers()`：このプロジェクトの時間主導トリガーを削除。

### 7) コード構成（単一ファイル）
- `run()`：本番実行（トリガーから呼ばれる）  
- `searchThreads_()`：Gmail検索  
- `buildEmbedPayload_()`：Embed生成  
- `postToDiscord_()`：Webhook POST + リトライ  
- `ensureProcessedLabel_()`：ラベル存在確認/作成  
- `markProcessed_()`：ラベル付与  
- `cleanupText_()`：本文プレビュー整形（改行正規化、過剰空白削減、引用/署名の簡易除去、DiscordのEmbed制限対策のトリム）  
- `getWebhookUrl_()` / `setWebhookUrl()`：Script Properties I/O  
- `createTimeTrigger()` / `deleteTriggers()` / `dryRun()` / `testOne()`

### 8) 受け入れ基準（満たすこと）
- **指定ラベル/検索条件の新着スレッドだけ**が対象になり、**各スレッドは1回だけ** #alerts に流れる。  
- Embed に **件名 / 差出人 / 本文プレビュー / メールリンク** が含まれる。  
- 失敗時はラベル付与しないため、次回に再送が試みられる。  
- 例外や一時的エラーがあっても他スレッド処理は継続。  
- `dryRun()` と `testOne()` で、安全に導入確認ができる。  
- 時間主導トリガー（例：10分ごと）で安定実行できる。

### 9) 導入メモ（コメントで記載）
- Apps Script エディタで **時刻タイムゾーンを Asia/Tokyo** に設定。  
- 最初に `setWebhookUrl("https://discord.com/api/webhooks/…")` を実行して保存。  
- `dryRun()` で対象確認 → `testOne()` でWebhook疎通確認 → `createTimeTrigger()` で定期実行開始。  
- `GMAIL_QUERY` の `newer_than` は **分単位不可**（日/週/月のみ）。必要に応じ実行間隔を短くしてカバーすること。  

---

**出力物**：  
1) 上記仕様を満たす **`Code.gs`（単一ファイル）** の完成コード（十分な日本語コメント付き）。  
2) ファイル冒頭コメントに **簡潔な導入手順・テスト手順** を記載。  
3) 文字数超過エラーやレート制限時の挙動についてもコメントで注意書き。
