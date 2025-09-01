/**
 * Gmail to Discord 自動連携スクリプト
 * 
 * ===== 導入手順 =====
 * 1. Google Apps Script エディタでプロジェクトを作成
 * 2. プロジェクト設定から タイムゾーンを "Asia/Tokyo" に変更
 * 3. このコードを Code.gs にコピー
 * 4. Discord Webhook を作成
 *    - Discord サーバー → 設定 → 連携サービス → ウェブフック
 *    - 「新しいウェブフック」→ #alerts チャンネル選択 → URL をコピー
 * 5. Gmail フィルタを作成（例）
 *    - Gmail → 設定 → フィルタとブロック中のアドレス
 *    - 条件例: 特定の送信者、件名キーワード
 *    - ラベル「ToDiscord」を適用するよう設定
 * 6. setWebhookUrl("https://discord.com/api/webhooks/...") を実行してWebhook URLを保存
 * 
 * ===== テスト手順 =====
 * 1. dryRun() を実行 → 対象メールがログに表示されることを確認
 * 2. testOne() を実行 → Discord にテストメッセージが届くことを確認
 * 3. run() を手動実行 → 実際のメールが Discord に投稿されることを確認
 * 4. createTimeTrigger() を実行 → 10分ごとの自動実行を開始
 * 
 * ===== 注意事項 =====
 * - newer_than は日(d)/週(w)/月(m)単位のみ対応（分単位は不可）
 * - Discord Embed の文字数制限: title(256), description(4096), field.value(1024)
 * - Discord Webhook のレート制限: 30リクエスト/分
 * - 処理済みラベルが付与されたメールは再送信されません
 */

// ===== 設定値 =====
const CONFIG = {
  // Gmail 検索クエリ（例: 特定ラベル、未読、チャット以外、2日以内）
  GMAIL_QUERY: 'label:ToDiscord -in:chats newer_than:2d',
  
  // 処理済みを示すラベル名（存在しない場合は自動作成）
  PROCESSED_LABEL: 'ToDiscord-処理済み',
  
  // 一度の実行で処理する最大スレッド数
  MAX_THREADS_PER_RUN: 30,
  
  // 本文プレビューの最大文字数
  PREVIEW_MAX_CHARS: 180,
  
  // タイムゾーン
  TIMEZONE: 'Asia/Tokyo',
  
  // Discord bot の表示名
  DISCORD_USERNAME: 'Gmail Alerts',
  
  // リトライ設定
  MAX_RETRY_COUNT: 3,
  RETRY_DELAY_MS: 1000,
  
  // メッセージ選択（true: 最新メッセージ, false: 最初のメッセージ）
  USE_LATEST_MESSAGE: true,
  
  // Gmail アカウントインデックス（複数アカウント使用時のリンク先制御）
  GMAIL_U_INDEX: 0,
  
  // スロットリング（Discord レート制限対策）
  THROTTLE_DELAY_MS: 200
};

/**
 * メイン実行関数（トリガーから呼ばれる）
 */
function run() {
  try {
    const webhookUrl = getWebhookUrl_();
    if (!webhookUrl) {
      console.error('Webhook URL が設定されていません。setWebhookUrl() を実行してください。');
      return;
    }
    
    // 処理済みラベルの確認/作成
    ensureProcessedLabel_();
    
    // 対象スレッドを検索（軽い障害時の再試行付き）
    let threads;
    try {
      threads = searchThreads_();
    } catch (error) {
      console.warn('Gmail検索に失敗しました。500ms後にリトライします:', error);
      Utilities.sleep(500);
      try {
        threads = searchThreads_();
        console.log('リトライに成功しました。');
      } catch (retryError) {
        console.error('リトライも失敗しました:', retryError);
        throw retryError;
      }
    }
    
    if (threads.length === 0) {
      console.log('Gmail検索は成功しましたが、処理対象のスレッドがありません。');
      return;
    }
    
    console.log(`${threads.length} 件のスレッドを処理します。`);
    
    let successCount = 0;
    let failCount = 0;
    
    // 各スレッドを処理
    threads.forEach((thread, index) => {
      try {
        // スロットリング（2件目以降）
        if (index > 0) {
          Utilities.sleep(CONFIG.THROTTLE_DELAY_MS);
        }
        
        // Embed ペイロードを構築
        const payload = buildEmbedPayload_(thread);
        
        // Discord に投稿
        const success = postToDiscord_(webhookUrl, payload);
        
        if (success) {
          // 成功時のみ処理済みラベルを付与
          markProcessed_(thread);
          successCount++;
          console.log(`✓ 送信成功: ${thread.getFirstMessageSubject()}`);
        } else {
          failCount++;
          console.error(`✗ 送信失敗: ${thread.getFirstMessageSubject()}`);
        }
        
      } catch (error) {
        failCount++;
        console.error(`スレッド処理エラー (ID: ${thread.getId()}):`, error);
        // エラーがあっても他のスレッドの処理は継続
      }
    });
    
    console.log(`処理完了: 成功 ${successCount} 件, 失敗 ${failCount} 件`);
    
  } catch (error) {
    console.error('実行エラー:', error);
    throw error;
  }
}

/**
 * Gmail スレッドを検索
 * @return {GmailThread[]} 対象スレッドの配列
 */
function searchThreads_() {
  // 処理済みラベルを除外するクエリを追加
  const query = `${CONFIG.GMAIL_QUERY} -label:"${CONFIG.PROCESSED_LABEL}"`;
  
  try {
    const threads = GmailApp.search(query, 0, CONFIG.MAX_THREADS_PER_RUN);
    return threads;
  } catch (error) {
    console.error('Gmail 検索エラー:', error);
    throw error;
  }
}

/**
 * Discord Embed ペイロードを構築
 * @param {GmailThread} thread - Gmail スレッド
 * @return {Object} Discord Webhook 用 JSON ペイロード
 */
function buildEmbedPayload_(thread) {
  // 最新/最初メッセージの切替
  const message = CONFIG.USE_LATEST_MESSAGE ? thread.getMessages().slice(-1)[0] : thread.getMessages()[0];
  const subject = thread.getFirstMessageSubject() || '(件名なし)';
  const from = message.getFrom() || '(差出人不明)';
  const date = message.getDate();
  const threadId = thread.getId();
  
  // Gmail へのリンク
  const gmailUrl = `https://mail.google.com/mail/u/${CONFIG.GMAIL_U_INDEX}/#inbox/${threadId}`;
  
  // 本文プレビューを取得・整形
  let bodyPreview = message.getPlainBody();
  bodyPreview = cleanupText_(bodyPreview);
  
  // Discord Embed の文字数制限に対応
  // Discord制限: title=256, description=4096, field.value=1024文字
  const truncatedSubject = subject.length > 256 ? subject.substring(0, 253) + '...' : subject;
  // description用：より長い制限を活用（ただしCONFIG設定を優先）
  const maxDescChars = Math.min(CONFIG.PREVIEW_MAX_CHARS, 4093); // 4096-3('...')=4093
  const truncatedPreview = bodyPreview.length > maxDescChars 
    ? bodyPreview.substring(0, maxDescChars - 3) + '...' 
    : bodyPreview;
  // fields.value用：1024文字制限
  const truncatedFrom = from.length > 1024 ? from.substring(0, 1021) + '...' : from;
  const truncatedQuery = CONFIG.GMAIL_QUERY.length > 1024 
    ? CONFIG.GMAIL_QUERY.substring(0, 1021) + '...' 
    : CONFIG.GMAIL_QUERY;
  
  // ISO8601 形式のタイムスタンプ
  const timestamp = Utilities.formatDate(date, CONFIG.TIMEZONE, "yyyy-MM-dd'T'HH:mm:ss'Z'");
  
  return {
    username: CONFIG.DISCORD_USERNAME,
    embeds: [{
      title: truncatedSubject,
      url: gmailUrl,
      description: truncatedPreview,
      fields: [
        {
          name: 'From',
          value: truncatedFrom,
          inline: true
        },
        {
          name: 'Query',
          value: truncatedQuery,
          inline: true
        }
      ],
      timestamp: timestamp,
      footer: {
        text: 'GAS Gmail→Discord'
      },
      color: 5814783 // 青系の色
    }]
  };
}

/**
 * Discord Webhook に POST（リトライ付き）
 * @param {string} webhookUrl - Discord Webhook URL
 * @param {Object} payload - 送信するペイロード
 * @return {boolean} 成功したかどうか
 */
function postToDiscord_(webhookUrl, payload) {
  const options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };
  
  for (let attempt = 1; attempt <= CONFIG.MAX_RETRY_COUNT; attempt++) {
    try {
      const response = UrlFetchApp.fetch(webhookUrl, options);
      const statusCode = response.getResponseCode();
      
      // 成功（204 No Content または 200 OK）
      if (statusCode === 204 || statusCode === 200) {
        return true;
      }
      
      // レート制限（429）の場合は待機時間を長くする
      if (statusCode === 429) {
        const retryAfter = response.getHeaders()['Retry-After'];
        const waitTime = retryAfter ? parseInt(retryAfter) * 1000 : CONFIG.RETRY_DELAY_MS * attempt * 2;
        console.log(`レート制限検出。${waitTime}ms 待機後リトライ (${attempt}/${CONFIG.MAX_RETRY_COUNT})`);
        Utilities.sleep(waitTime);
        continue;
      }
      
      // その他のエラー
      console.error(`Discord API エラー (attempt ${attempt}/${CONFIG.MAX_RETRY_COUNT}):`, 
                    `Status: ${statusCode}`, 
                    `Response: ${response.getContentText()}`);
      
      // 4xx エラーの場合はリトライしない（リクエスト自体が不正）
      if (statusCode >= 400 && statusCode < 500 && statusCode !== 429) {
        return false;
      }
      
      // 5xx エラーの場合はリトライ
      if (attempt < CONFIG.MAX_RETRY_COUNT) {
        const waitTime = CONFIG.RETRY_DELAY_MS * attempt;
        Utilities.sleep(waitTime);
      }
      
    } catch (error) {
      console.error(`Discord 送信エラー (attempt ${attempt}/${CONFIG.MAX_RETRY_COUNT}):`, error);
      if (attempt < CONFIG.MAX_RETRY_COUNT) {
        Utilities.sleep(CONFIG.RETRY_DELAY_MS * attempt);
      }
    }
  }
  
  return false;
}

/**
 * 処理済みラベルの存在確認と作成
 */
function ensureProcessedLabel_() {
  try {
    const label = GmailApp.getUserLabelByName(CONFIG.PROCESSED_LABEL);
    if (!label) {
      GmailApp.createLabel(CONFIG.PROCESSED_LABEL);
      console.log(`ラベル "${CONFIG.PROCESSED_LABEL}" を作成しました。`);
    }
  } catch (error) {
    console.error('ラベル作成エラー:', error);
    throw error;
  }
}

/**
 * スレッドに処理済みラベルを付与
 * @param {GmailThread} thread - 対象スレッド
 */
function markProcessed_(thread) {
  try {
    const label = GmailApp.getUserLabelByName(CONFIG.PROCESSED_LABEL);
    thread.addLabel(label);
  } catch (error) {
    console.error('ラベル付与エラー:', error);
    throw error;
  }
}

/**
 * 本文テキストを整形（改行・空白正規化、引用・署名の簡易除去、Discord対応）
 * @param {string} text - 元のテキスト
 * @return {string} 整形後のテキスト
 */
function cleanupText_(text) {
  if (!text) return '';
  
  // HTML タグを除去（簡易的）
  text = text.replace(/<[^>]*>/g, '');
  
  // 引用部分を除去（> で始まる行）
  text = text.split('\n')
    .filter(line => !line.trim().startsWith('>'))
    .join('\n');
  
  // 署名を除去（-- 以降）
  const signatureIndex = text.indexOf('\n--\n');
  if (signatureIndex > -1) {
    text = text.substring(0, signatureIndex);
  }
  
  // 返信の区切り線を除去
  text = text.replace(/_{10,}/g, '');
  text = text.replace(/-{10,}/g, '');
  text = text.replace(/={10,}/g, '');
  
  // 改行を正規化
  text = text.replace(/\r\n/g, '\n');
  text = text.replace(/\r/g, '\n');
  
  // 連続する改行を最大2つまでに圧縮
  text = text.replace(/\n{3,}/g, '\n\n');
  
  // 全角空白・タブを半角スペースに正規化
  text = text.replace(/[\u3000\t]/g, ' ');
  
  // 連続する空白を1つに圧縮
  text = text.replace(/ {2,}/g, ' ');
  
  // 前後の空白を削除
  text = text.trim();
  
  return text;
}

/**
 * Script Properties から Webhook URL を取得
 * @return {string|null} Webhook URL
 */
function getWebhookUrl_() {
  const scriptProperties = PropertiesService.getScriptProperties();
  return scriptProperties.getProperty('DISCORD_WEBHOOK_URL');
}

/**
 * Script Properties に Webhook URL を保存
 * @param {string} url - Discord Webhook URL
 */
function setWebhookUrl(url) {
  if (!url || !url.startsWith('https://discord.com/api/webhooks/')) {
    throw new Error('有効な Discord Webhook URL を指定してください。');
  }
  
  const scriptProperties = PropertiesService.getScriptProperties();
  scriptProperties.setProperty('DISCORD_WEBHOOK_URL', url);
  console.log('Webhook URL を保存しました。');
}

// ===== ユーティリティ関数 =====

/**
 * ドライラン（実際には送信せず、対象を確認）
 */
function dryRun() {
  ensureProcessedLabel_();
  const threads = searchThreads_();
  
  if (threads.length === 0) {
    console.log('処理対象のスレッドがありません。');
    return;
  }
  
  console.log(`===== ドライラン結果 =====`);
  console.log(`USE_LATEST_MESSAGE: ${CONFIG.USE_LATEST_MESSAGE} (${CONFIG.USE_LATEST_MESSAGE ? '最新' : '最初'}のメッセージ)`);
  console.log(`GMAIL_U_INDEX: ${CONFIG.GMAIL_U_INDEX} (アカウントインデックス)`);
  console.log(`対象スレッド数: ${threads.length} 件`);
  console.log(`検索クエリ: ${CONFIG.GMAIL_QUERY} -label:"${CONFIG.PROCESSED_LABEL}"`);
  console.log('');
  
  threads.forEach((thread, index) => {
    // buildEmbedPayload_() と同じロジック
    const message = CONFIG.USE_LATEST_MESSAGE ? thread.getMessages().slice(-1)[0] : thread.getMessages()[0];
    const subject = thread.getFirstMessageSubject() || '(件名なし)';
    const from = message.getFrom() || '(差出人不明)';
    const threadId = thread.getId();
    const gmailUrl = `https://mail.google.com/mail/u/${CONFIG.GMAIL_U_INDEX}/#inbox/${threadId}`;
    
    console.log(`[${index + 1}] ${subject}`);
    console.log(`    From: ${from}`);
    console.log(`    URL: ${gmailUrl}`);
    console.log('');
  });
}

/**
 * テスト送信（ダミーメッセージを1件送信）
 */
function testOne() {
  const webhookUrl = getWebhookUrl_();
  if (!webhookUrl) {
    console.error('Webhook URL が設定されていません。setWebhookUrl() を実行してください。');
    return;
  }
  
  // 新機能のテスト要素を追加
  const testPayload = {
    username: CONFIG.DISCORD_USERNAME,
    embeds: [{
      title: 'テストメッセージ - 新機能確認',
      url: `https://mail.google.com/mail/u/${CONFIG.GMAIL_U_INDEX}/#inbox`,
      description: `これは Gmail to Discord 連携のテストメッセージです。\nこのメッセージが表示されれば、Webhook の設定は正常です。\n\n【設定確認】\n・USE_LATEST_MESSAGE: ${CONFIG.USE_LATEST_MESSAGE}\n・GMAIL_U_INDEX: ${CONFIG.GMAIL_U_INDEX}\n・文字数制限テスト:　　全角空白→半角変換済み`,
      fields: [
        {
          name: 'From',
          value: 'test@example.com (テスト送信者)',
          inline: true
        },
        {
          name: 'Config',
          value: `Query: ${CONFIG.GMAIL_QUERY.length > 50 ? CONFIG.GMAIL_QUERY.substring(0, 47) + '...' : CONFIG.GMAIL_QUERY}`,
          inline: true
        }
      ],
      timestamp: new Date().toISOString(),
      footer: {
        text: 'GAS Gmail→Discord (テスト)'
      },
      color: 3066993 // 緑系の色
    }]
  };
  
  console.log('テストメッセージを送信中...');
  const success = postToDiscord_(webhookUrl, testPayload);
  
  if (success) {
    console.log('✓ テストメッセージの送信に成功しました。Discord を確認してください。');
  } else {
    console.error('✗ テストメッセージの送信に失敗しました。Webhook URL を確認してください。');
  }
}

/**
 * 時間主導トリガーを作成（10分ごと）
 */
function createTimeTrigger() {
  // 既存のトリガーを確認
  const triggers = ScriptApp.getProjectTriggers();
  const existingTrigger = triggers.find(trigger => 
    trigger.getHandlerFunction() === 'run' && 
    trigger.getEventType() === ScriptApp.EventType.CLOCK
  );
  
  if (existingTrigger) {
    console.log('既にトリガーが設定されています。');
    return;
  }
  
  // 新しいトリガーを作成
  ScriptApp.newTrigger('run')
    .timeBased()
    .everyMinutes(10)
    .create();
  
  console.log('10分ごとの時間主導トリガーを作成しました。');
}

/**
 * このプロジェクトの時間主導トリガーをすべて削除
 */
function deleteTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  let count = 0;
  
  triggers.forEach(trigger => {
    if (trigger.getEventType() === ScriptApp.EventType.CLOCK) {
      ScriptApp.deleteTrigger(trigger);
      count++;
    }
  });
  
  console.log(`${count} 個のトリガーを削除しました。`);
}

/**
 * 設定値を確認
 */
function showConfig() {
  console.log('===== 現在の設定 =====');
  console.log('GMAIL_QUERY:', CONFIG.GMAIL_QUERY);
  console.log('PROCESSED_LABEL:', CONFIG.PROCESSED_LABEL);
  console.log('MAX_THREADS_PER_RUN:', CONFIG.MAX_THREADS_PER_RUN);
  console.log('PREVIEW_MAX_CHARS:', CONFIG.PREVIEW_MAX_CHARS);
  console.log('TIMEZONE:', CONFIG.TIMEZONE);
  console.log('USE_LATEST_MESSAGE:', CONFIG.USE_LATEST_MESSAGE);
  console.log('GMAIL_U_INDEX:', CONFIG.GMAIL_U_INDEX);
  console.log('DISCORD_USERNAME:', CONFIG.DISCORD_USERNAME);
  console.log('Webhook URL 設定済み:', getWebhookUrl_() ? 'はい' : 'いいえ');
}