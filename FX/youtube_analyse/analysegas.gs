/**
 * 日本FX特化YouTube分析システム
 * Google Apps Script + YouTube Data API v3
 * 
 * 主な機能:
 * - 日本のFX関連YouTubeチャンネル発見・分析（1000人以上限定）
 * - 自動ダッシュボード生成
 * - AI質問機能（自然言語Q&A）
 * - 簡易モード（UI簡素化）
 */

// =============================================================================
// グローバル設定
// =============================================================================

var SHEET_NAMES = {
  SEARCH_TERMS: '検索語',
  DISCOVERED_CHANNELS: '発見チャンネル',
  TARGET_CHANNELS: '分析対象チャンネル',
  DASHBOARD: 'ダッシュボード',
  SETTINGS: '設定',
  LOG: 'ログ',
  // 内部処理用（簡易モード時は非表示）
  VIDEO_LIST: '動画一覧',
  DAILY_SNAPSHOT: '日次スナップ',
  DERIVED_KPI: '派生KPI',
  TITLE_ANALYSIS: 'タイトル分析',
  CHANNEL_SCORE: 'チャンネルスコア',
  WEEKDAY_HOUR: '曜日×時間帯分析',
  COMMENTS: 'コメント関連'
};

var FX_KEYWORDS = [
  "FX", "為替", "ドル円", "USDJPY", "EURJPY", "ポンド円", "トレード", "スキャル", 
  "デイトレ", "テクニカル分析", "移動平均", "RSI", "MACD", "ボリンジャー", "フィボ", 
  "サポレジ", "プライスアクション", "ダウ理論", "通貨", "外国為替", "スプレッド",
  "ロング", "ショート", "レバレッジ", "証拠金", "pips", "経済指標"
];

var SIMPLE_MODE_SHEETS = [
  SHEET_NAMES.SEARCH_TERMS,
  SHEET_NAMES.DISCOVERED_CHANNELS,
  SHEET_NAMES.TARGET_CHANNELS,
  SHEET_NAMES.DASHBOARD,
  SHEET_NAMES.SETTINGS,
  SHEET_NAMES.LOG
];

// =============================================================================
// メニュー作成
// =============================================================================

function onOpen() {
  var ui = SpreadsheetApp.getUi();
  ui.createMenu('🎯 日本FX YouTube分析')
    .addItem('0. 初期セットアップガイド', 'showSetupGuide')
    .addSeparator()
    .addItem('1. 競合発見（日本FX特化）', 'discoverChannels')
    .addItem('2a. 全取得チャンネル詳細更新', 'updateAllChannelDetails')
    .addItem('2b. 人気順で抽出', 'extractTopChannels')
    .addSeparator()
    .addItem('3. メトリクス取得（低負荷）', 'fetchPublicMetricsLowQuota')
    .addItem('4. 詳細動画一覧更新', 'updateVideoDetails')
    .addItem('5. 日次スナップショット', 'snapshotPublicMetrics')
    .addSeparator()
    .addItem('9. ダッシュボード初期化', 'seedDashboard')
    .addItem('ダッシュボード再生成', 'regenerateDashboard')
    .addItem('AIに要約してもらう（ダッシュボード）', 'generateAISummary')
    .addSeparator()
    .addItem('簡易モード ON/OFF', 'toggleSimpleMode')
    .addItem('環境診断（Health Check）', 'healthCheck')
    .create();
  
  // 初回実行時のシート初期化
  initializeSheets();
}

// =============================================================================
// 初期セットアップ
// =============================================================================

function showSetupGuide() {
  var ui = SpreadsheetApp.getUi();
  var message = `🚀 日本FX YouTube分析システム - 初期セットアップガイド\n\n` +
    `【必要な設定】\n` +
    `1. YouTube Data API v3の有効化\n` +
    `   - GCPコンソール → APIs & Services → Library → YouTube Data API v3を有効化\n\n` +
    `2. Advanced Google Servicesの有効化\n` +
    `   - スクリプトエディタ → サービス → YouTube Data API v3を追加\n\n` +
    `3. APIキーの設定\n` +
    `   - 「設定」シートのAPIKEY行にYouTube Data API v3のキーを入力\n\n` +
    `4. AI機能（オプション）\n` +
    `   - 「設定」シートのANTHROPIC_API_KEY行にClaude APIキーを入力\n\n` +
    `【初回実行手順】\n` +
    `1. 「検索語」シートでキーワード設定\n` +
    `2. 「1. 競合発見」を実行\n` +
    `3. 「2b. 人気順で抽出」で対象選定\n` +
    `4. 「3→4→5」の順で詳細分析\n` +
    `5. 「9. ダッシュボード初期化」でグラフ生成\n\n` +
    `詳細は「ログ」シートで進捗確認できます。`;
    
  ui.alert('セットアップガイド', message, ui.ButtonSet.OK);
}

function healthCheck() {
  var ui = SpreadsheetApp.getUi();
  var issues = [];
  var successes = [];
  
  // APIキー確認
  try {
    var settings = getSettings();
    if (settings.APIKEY) {
      successes.push('✅ YouTube Data API キーが設定済み');
    } else {
      issues.push('❌ YouTube Data API キーが未設定');
    }
    
    if (settings.ANTHROPIC_API_KEY) {
      successes.push('✅ Anthropic API キーが設定済み');
    } else {
      issues.push('⚠️ Anthropic API キー未設定（AI機能無効）');
    }
  } catch (e) {
    issues.push('❌ 設定読み込みエラー: ' + e.toString());
  }
  
  // Advanced Services確認
  try {
    YouTube.Search.list('snippet', {q: 'test', maxResults: 1});
    successes.push('✅ YouTube Advanced Service有効');
  } catch (e) {
    issues.push('❌ YouTube Advanced Service無効または設定不備');
  }
  
  var result = '🔍 環境診断結果\n\n【正常】\n' + successes.join('\n') + 
               '\n\n【問題・注意】\n' + issues.join('\n');
  
  ui.alert('環境診断', result, ui.ButtonSet.OK);
  logMessage('環境診断実行: ' + issues.length + '件の問題を検出');
}

function initializeSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 基本シートの作成
  createSheetIfNotExists(SHEET_NAMES.SEARCH_TERMS, [
    ['検索語', '説明'],
    ['FX', 'FX全般'],
    ['為替', '為替取引'],
    ['ドル円', 'USD/JPY'],
    ['テクニカル分析', 'チャート分析'],
    ['移動平均', 'テクニカル指標'],
    ['RSI', 'テクニカル指標'],
    ['MACD', 'テクニカル指標'],
    ['ボリンジャー', 'ボリンジャーバンド'],
    ['フィボ', 'フィボナッチ'],
    ['サポレジ', 'サポート・レジスタンス'],
    ['スキャル', 'スキャルピング'],
    ['デイトレ', 'デイトレード']
  ]);
  
  createSheetIfNotExists(SHEET_NAMES.DISCOVERED_CHANNELS, [
    ['チャンネルID', 'チャンネル名', 'チャンネルURL', '登録者数', '総再生数', '動画本数', '国', 'FX関連スコア', '直近投稿(JST)', '直近投稿から日数', 'トップ動画タイトル', 'トップ動画URL', 'トップ動画再生数', 'PopularityScore']
  ]);
  
  createSheetIfNotExists(SHEET_NAMES.TARGET_CHANNELS, [
    ['チャンネルID', 'チャンネル名', 'チャンネルURL', 'メモ']
  ]);
  
  createSheetIfNotExists(SHEET_NAMES.DASHBOARD, [
    ['項目', '値', '説明'],
    ['最終更新', '', ''],
    ['総発見チャンネル数', '', ''],
    ['分析対象数', '', ''],
    ['平均登録者数', '', ''],
    ['', '', ''],
    ['=== AI要約 ===', '', ''],
    ['主要トレンド', '', 'AIによる分析結果']
  ]);
  
  createSheetIfNotExists(SHEET_NAMES.SETTINGS, [
    ['設定項目', '値', '説明'],
    ['APIKEY', '', 'YouTube Data API v3 キー'],
    ['ANTHROPIC_API_KEY', '', 'Claude API キー（AI機能用）'],
    ['OPENAI_API_KEY', '', 'OpenAI API キー（AI機能用・予備）'],
    ['MAX_CHANNELS', '500', '最大取得チャンネル数'],
    ['MIN_SUBSCRIBERS', '1000', '最小登録者数'],
    ['FX_SCORE_THRESHOLD', '2', 'FX関連判定しきい値'],
    ['SIMPLE_MODE', 'ON', '簡易モード（ON/OFF）']
  ]);
  
  createSheetIfNotExists(SHEET_NAMES.LOG, [
    ['日時', 'レベル', 'メッセージ', '詳細']
  ]);
  
  // 内部処理用シート
  createSheetIfNotExists(SHEET_NAMES.VIDEO_LIST, [
    ['チャンネルID', '動画ID', 'タイトル', '投稿日', '再生数', 'いいね数', 'コメント数', '説明']
  ]);
  
  createSheetIfNotExists(SHEET_NAMES.DAILY_SNAPSHOT, [
    ['日付', 'チャンネルID', '登録者数', '総再生数', '動画数']
  ]);
  
  // 簡易モード設定の適用
  var settings = getSettings();
  if (settings.SIMPLE_MODE === 'ON') {
    applySimpleMode(true);
  }
  
  logMessage('シート初期化完了');
}

function createSheetIfNotExists(name, headers) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(name);
  
  if (!sheet) {
    sheet = ss.insertSheet(name);
    if (headers && headers.length > 0) {
      sheet.getRange(1, 1, headers.length, headers[0].length).setValues(headers);
      sheet.getRange(1, 1, 1, headers[0].length).setFontWeight('bold');
    }
  }
  return sheet;
}

// =============================================================================
// 設定管理
// =============================================================================

function getSettings() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.SETTINGS);
  var data = sheet.getDataRange().getValues();
  var settings = {};
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] && data[i][1] !== '') {
      settings[data[i][0]] = data[i][1];
    }
  }
  return settings;
}

function updateSetting(key, value) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.SETTINGS);
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === key) {
      sheet.getRange(i + 1, 2).setValue(value);
      return;
    }
  }
  
  // 設定が見つからない場合は新規追加
  sheet.appendRow([key, value, '']);
}

// =============================================================================
// 簡易モード
// =============================================================================

function toggleSimpleMode() {
  var settings = getSettings();
  var currentMode = settings.SIMPLE_MODE || 'OFF';
  var newMode = (currentMode === 'ON') ? 'OFF' : 'ON';
  
  updateSetting('SIMPLE_MODE', newMode);
  applySimpleMode(newMode === 'ON');
  
  var ui = SpreadsheetApp.getUi();
  ui.alert('簡易モード', '簡易モードを' + newMode + 'にしました。', ui.ButtonSet.OK);
  logMessage('簡易モード切り替え: ' + newMode);
}

function applySimpleMode(isSimple) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheets = ss.getSheets();
  
  for (var i = 0; i < sheets.length; i++) {
    var sheet = sheets[i];
    var sheetName = sheet.getName();
    
    if (isSimple) {
      // 簡易モード: 指定シート以外を非表示
      var shouldShow = SIMPLE_MODE_SHEETS.indexOf(sheetName) !== -1;
      sheet.showSheet();
      if (!shouldShow) {
        sheet.hideSheet();
      }
    } else {
      // 通常モード: 全シート表示
      sheet.showSheet();
    }
  }
  
  // シート順序の調整
  reorderSheets();
}

function reorderSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var desiredOrder = [
    SHEET_NAMES.SEARCH_TERMS,
    SHEET_NAMES.DISCOVERED_CHANNELS,
    SHEET_NAMES.TARGET_CHANNELS,
    SHEET_NAMES.DASHBOARD,
    SHEET_NAMES.SETTINGS,
    SHEET_NAMES.LOG
  ];
  
  for (var i = 0; i < desiredOrder.length; i++) {
    var sheet = ss.getSheetByName(desiredOrder[i]);
    if (sheet) {
      ss.moveSheet(sheet, i + 1);
    }
  }
}

// =============================================================================
// YouTube API関連
// =============================================================================

function discoverChannels() {
  logMessage('競合発見開始（日本FX特化）');
  
  var settings = getSettings();
  var maxChannels = parseInt(settings.MAX_CHANNELS) || 500;
  var minSubscribers = parseInt(settings.MIN_SUBSCRIBERS) || 1000;
  var fxThreshold = parseInt(settings.FX_SCORE_THRESHOLD) || 2;
  
  var searchTerms = getSearchTerms();
  var allChannels = {};
  var processedCount = 0;
  
  try {
    // 各検索語でチャンネルを発見
    for (var i = 0; i < searchTerms.length && processedCount < maxChannels; i++) {
      var term = searchTerms[i];
      logMessage('検索実行: ' + term);
      
      var channels = searchChannelsForTerm_jpfx(term, Math.min(50, maxChannels - processedCount));
      
      for (var channelId in channels) {
        if (!allChannels[channelId] && processedCount < maxChannels) {
          var channelData = channels[channelId];
          
          // FX関連性とフィルタリング
          var fxScore = calculateFxScore_jpfx(channelData);
          if (fxScore >= fxThreshold && channelData.subscriberCount >= minSubscribers) {
            channelData.fxScore = fxScore;
            allChannels[channelId] = channelData;
            processedCount++;
          }
        }
      }
    }
    
    // 結果をシートに書き込み
    writeDiscoveredChannels(allChannels);
    
    logMessage('競合発見完了: ' + processedCount + '件のチャンネルを発見');
    SpreadsheetApp.getUi().alert('完了', processedCount + '件のFX関連チャンネルを発見しました。', SpreadsheetApp.getUi().ButtonSet.OK);
    
  } catch (error) {
    logMessage('エラー', 'ERROR', error.toString());
    throw error;
  }
}

function searchChannelsForTerm_jpfx(searchTerm, maxResults) {
  var channels = {};
  var nextPageToken = '';
  var totalFetched = 0;
  
  while (totalFetched < maxResults && nextPageToken !== null) {
    var searchResponse = exponentialBackoff(function() {
      return YouTube.Search.list('snippet', {
        q: searchTerm,
        type: 'channel',
        regionCode: 'JP',
        relevanceLanguage: 'ja',
        maxResults: Math.min(50, maxResults - totalFetched),
        pageToken: nextPageToken || undefined
      });
    });
    
    if (searchResponse.items) {
      var channelIds = searchResponse.items.map(function(item) {
        return item.snippet.channelId;
      });
      
      // チャンネル詳細を取得
      var detailsResponse = exponentialBackoff(function() {
        return YouTube.Channels.list('snippet,statistics,contentDetails', {
          id: channelIds.join(',')
        });
      });
      
      if (detailsResponse.items) {
        for (var i = 0; i < detailsResponse.items.length; i++) {
          var channel = detailsResponse.items[i];
          var subscriberCount = parseInt(channel.statistics.subscriberCount) || 0;
          
          // 1000人以上のフィルタ
          if (subscriberCount >= 1000) {
            channels[channel.id] = {
              id: channel.id,
              title: channel.snippet.title,
              description: channel.snippet.description || '',
              customUrl: channel.snippet.customUrl || '',
              country: channel.snippet.country || '',
              subscriberCount: subscriberCount,
              videoCount: parseInt(channel.statistics.videoCount) || 0,
              viewCount: parseInt(channel.statistics.viewCount) || 0,
              publishedAt: channel.snippet.publishedAt
            };
          }
        }
      }
      
      totalFetched += searchResponse.items.length;
    }
    
    nextPageToken = searchResponse.nextPageToken || null;
  }
  
  return channels;
}

function calculateFxScore_jpfx(channelData) {
  var score = 0;
  var text = (channelData.title + ' ' + channelData.description).toLowerCase();
  
  // FXキーワードによるスコアリング
  for (var i = 0; i < FX_KEYWORDS.length; i++) {
    var keyword = FX_KEYWORDS[i].toLowerCase();
    var matches = text.split(keyword).length - 1;
    score += matches;
  }
  
  // 日本語判定（ひらがな・カタカナ・漢字の存在）
  if (/[ひらがなカタカナ漢字]/.test(channelData.title)) {
    score += 1;
  }
  
  // 英語主体チャンネルの減点
  var englishRatio = (text.match(/[a-z]/g) || []).length / text.length;
  if (englishRatio > 0.7) {
    score -= 2;
  }
  
  return score;
}

function getSearchTerms() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.SEARCH_TERMS);
  var data = sheet.getDataRange().getValues();
  var terms = [];
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0]) {
      terms.push(data[i][0]);
    }
  }
  
  return terms;
}

function writeDiscoveredChannels(channels) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  
  // 既存データをクリア（ヘッダーは残す）
  if (sheet.getLastRow() > 1) {
    sheet.deleteRows(2, sheet.getLastRow() - 1);
  }
  
  var rows = [];
  for (var channelId in channels) {
    var channel = channels[channelId];
    var channelUrl = generateChannelUrl(channel);
    
    // 最新動画情報を取得（可能であれば）
    var latestVideo = getLatestVideoInfo(channelId);
    var daysSinceUpload = latestVideo ? Math.floor((new Date() - new Date(latestVideo.publishedAt)) / (1000 * 60 * 60 * 24)) : '';
    
    rows.push([
      channel.id,
      channel.title,
      channelUrl,
      channel.subscriberCount,
      channel.viewCount,
      channel.videoCount,
      channel.country || 'JP',
      channel.fxScore || 0,
      latestVideo ? formatJST(latestVideo.publishedAt) : '',
      daysSinceUpload,
      latestVideo ? latestVideo.title : '',
      latestVideo ? 'https://www.youtube.com/watch?v=' + latestVideo.videoId : '',
      latestVideo ? latestVideo.viewCount : '',
      calculatePopularityScore(channel)
    ]);
  }
  
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, 14).setValues(rows);
  }
}

function generateChannelUrl(channel) {
  if (channel.customUrl) {
    return 'https://www.youtube.com/@' + channel.customUrl;
  } else {
    return 'https://www.youtube.com/channel/' + channel.id;
  }
}

function getLatestVideoInfo(channelId) {
  try {
    var searchResponse = exponentialBackoff(function() {
      return YouTube.Search.list('snippet', {
        channelId: channelId,
        type: 'video',
        order: 'date',
        maxResults: 1
      });
    });
    
    if (searchResponse.items && searchResponse.items.length > 0) {
      var video = searchResponse.items[0];
      
      // 動画詳細を取得
      var videoDetails = exponentialBackoff(function() {
        return YouTube.Videos.list('statistics', {
          id: video.id.videoId
        });
      });
      
      return {
        videoId: video.id.videoId,
        title: video.snippet.title,
        publishedAt: video.snippet.publishedAt,
        viewCount: videoDetails.items[0] ? parseInt(videoDetails.items[0].statistics.viewCount) || 0 : 0
      };
    }
  } catch (error) {
    logMessage('最新動画取得エラー', 'WARN', 'チャンネルID: ' + channelId);
  }
  return null;
}

function calculatePopularityScore(channel) {
  // 簡易的な人気度スコア計算
  var subscriberScore = Math.log10(channel.subscriberCount || 1);
  var viewScore = Math.log10((channel.viewCount || 1) / (channel.videoCount || 1));
  return Math.round((subscriberScore + viewScore) * 10) / 10;
}

function extractTopChannels() {
  var discoveredSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  var targetSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.TARGET_CHANNELS);
  
  var data = discoveredSheet.getDataRange().getValues();
  if (data.length <= 1) {
    SpreadsheetApp.getUi().alert('エラー', '発見チャンネルが存在しません。先に「1. 競合発見」を実行してください。', SpreadsheetApp.getUi().ButtonSet.OK);
    return;
  }
  
  // PopularityScoreでソート（降順）
  var channels = [];
  for (var i = 1; i < data.length; i++) {
    channels.push({
      id: data[i][0],
      name: data[i][1],
      url: data[i][2],
      popularityScore: parseFloat(data[i][13]) || 0
    });
  }
  
  channels.sort(function(a, b) {
    return b.popularityScore - a.popularityScore;
  });
  
  // 上位20件を抽出対象に設定
  var topChannels = channels.slice(0, 20);
  
  // 既存データをクリア
  if (targetSheet.getLastRow() > 1) {
    targetSheet.deleteRows(2, targetSheet.getLastRow() - 1);
  }
  
  var rows = [];
  for (var i = 0; i < topChannels.length; i++) {
    var channel = topChannels[i];
    rows.push([channel.id, channel.name, channel.url, '人気上位' + (i + 1) + '位']);
  }
  
  if (rows.length > 0) {
    targetSheet.getRange(2, 1, rows.length, 4).setValues(rows);
  }
  
  logMessage('上位チャンネル抽出完了: ' + topChannels.length + '件');
  SpreadsheetApp.getUi().alert('完了', topChannels.length + '件の上位チャンネルを分析対象に設定しました。', SpreadsheetApp.getUi().ButtonSet.OK);
}

// =============================================================================
// メトリクス取得・更新
// =============================================================================

function updateAllChannelDetails() {
  logMessage('全チャンネル詳細更新開始');
  
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  var data = sheet.getDataRange().getValues();
  
  if (data.length <= 1) {
    logMessage('更新対象チャンネルなし');
    return;
  }
  
  var updatedCount = 0;
  for (var i = 1; i < data.length; i++) {
    var channelId = data[i][0];
    if (channelId) {
      try {
        updateChannelMetrics(channelId, i + 1, sheet);
        updatedCount++;
        
        // APIクォータ節約のため少し待機
        if (updatedCount % 10 === 0) {
          Utilities.sleep(1000);
        }
      } catch (error) {
        logMessage('チャンネル更新エラー', 'ERROR', 'ID: ' + channelId + ', Error: ' + error.toString());
      }
    }
  }
  
  logMessage('全チャンネル詳細更新完了: ' + updatedCount + '件');
}

function updateChannelMetrics(channelId, rowIndex, sheet) {
  var channelResponse = exponentialBackoff(function() {
    return YouTube.Channels.list('statistics,snippet', {
      id: channelId
    });
  });
  
  if (channelResponse.items && channelResponse.items.length > 0) {
    var channel = channelResponse.items[0];
    var stats = channel.statistics;
    
    // 登録者数、総再生数、動画本数を更新
    sheet.getRange(rowIndex, 4).setValue(parseInt(stats.subscriberCount) || 0);
    sheet.getRange(rowIndex, 5).setValue(parseInt(stats.viewCount) || 0);
    sheet.getRange(rowIndex, 6).setValue(parseInt(stats.videoCount) || 0);
    
    // 最新動画情報も更新
    var latestVideo = getLatestVideoInfo(channelId);
    if (latestVideo) {
      var daysSinceUpload = Math.floor((new Date() - new Date(latestVideo.publishedAt)) / (1000 * 60 * 60 * 24));
      sheet.getRange(rowIndex, 9).setValue(formatJST(latestVideo.publishedAt));
      sheet.getRange(rowIndex, 10).setValue(daysSinceUpload);
      sheet.getRange(rowIndex, 11).setValue(latestVideo.title);
      sheet.getRange(rowIndex, 12).setValue('https://www.youtube.com/watch?v=' + latestVideo.videoId);
      sheet.getRange(rowIndex, 13).setValue(latestVideo.viewCount);
    }
  }
}

function fetchPublicMetricsLowQuota() {
  logMessage('低負荷メトリクス取得開始');
  
  var targetSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.TARGET_CHANNELS);
  var data = targetSheet.getDataRange().getValues();
  
  if (data.length <= 1) {
    SpreadsheetApp.getUi().alert('エラー', '分析対象チャンネルが設定されていません。', SpreadsheetApp.getUi().ButtonSet.OK);
    return;
  }
  
  var processedCount = 0;
  for (var i = 1; i < data.length; i++) {
    var channelId = data[i][0];
    if (channelId) {
      try {
        // 基本メトリクスの更新
        updateChannelBasicMetrics(channelId);
        processedCount++;
        
        // APIクォータ節約
        Utilities.sleep(500);
      } catch (error) {
        logMessage('メトリクス取得エラー', 'ERROR', 'ID: ' + channelId);
      }
    }
  }
  
  logMessage('低負荷メトリクス取得完了: ' + processedCount + '件');
  SpreadsheetApp.getUi().alert('完了', processedCount + '件のチャンネルメトリクスを更新しました。', SpreadsheetApp.getUi().ButtonSet.OK);
}

function updateChannelBasicMetrics(channelId) {
  // 発見チャンネルシートの該当行を更新
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  var data = sheet.getDataRange().getValues();
  
  for (var i = 1; i < data.length; i++) {
    if (data[i][0] === channelId) {
      updateChannelMetrics(channelId, i + 1, sheet);
      break;
    }
  }
}

function updateVideoDetails() {
  logMessage('動画詳細更新開始');
  
  var targetSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.TARGET_CHANNELS);
  var videoSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.VIDEO_LIST);
  var data = targetSheet.getDataRange().getValues();
  
  // 既存動画データをクリア
  if (videoSheet.getLastRow() > 1) {
    videoSheet.deleteRows(2, videoSheet.getLastRow() - 1);
  }
  
  var allVideos = [];
  var processedCount = 0;
  
  for (var i = 1; i < data.length; i++) {
    var channelId = data[i][0];
    if (channelId) {
      try {
        var videos = getChannelVideos(channelId, 10); // 最新10本
        allVideos = allVideos.concat(videos);
        processedCount++;
        
        // APIクォータ節約
        Utilities.sleep(1000);
      } catch (error) {
        logMessage('動画取得エラー', 'ERROR', 'チャンネルID: ' + channelId);
      }
    }
  }
  
  // 動画データを書き込み
  if (allVideos.length > 0) {
    videoSheet.getRange(2, 1, allVideos.length, 8).setValues(allVideos);
  }
  
  logMessage('動画詳細更新完了: ' + allVideos.length + '本の動画を取得');
  SpreadsheetApp.getUi().alert('完了', allVideos.length + '本の動画詳細を更新しました。', SpreadsheetApp.getUi().ButtonSet.OK);
}

function getChannelVideos(channelId, maxResults) {
  var videos = [];
  var nextPageToken = '';
  var totalFetched = 0;
  
  while (totalFetched < maxResults && nextPageToken !== null) {
    var searchResponse = exponentialBackoff(function() {
      return YouTube.Search.list('snippet', {
        channelId: channelId,
        type: 'video',
        order: 'date',
        maxResults: Math.min(25, maxResults - totalFetched),
        pageToken: nextPageToken || undefined
      });
    });
    
    if (searchResponse.items) {
      var videoIds = searchResponse.items.map(function(item) {
        return item.id.videoId;
      });
      
      // 動画詳細を取得
      var videoDetails = exponentialBackoff(function() {
        return YouTube.Videos.list('snippet,statistics', {
          id: videoIds.join(',')
        });
      });
      
      if (videoDetails.items) {
        for (var i = 0; i < videoDetails.items.length; i++) {
          var video = videoDetails.items[i];
          var stats = video.statistics;
          
          videos.push([
            channelId,
            video.id,
            video.snippet.title,
            formatJST(video.snippet.publishedAt),
            parseInt(stats.viewCount) || 0,
            parseInt(stats.likeCount) || 0,
            parseInt(stats.commentCount) || 0,
            (video.snippet.description || '').substring(0, 200) + '...'
          ]);
        }
      }
      
      totalFetched += searchResponse.items.length;
    }
    
    nextPageToken = searchResponse.nextPageToken || null;
  }
  
  return videos;
}

function snapshotPublicMetrics() {
  logMessage('日次スナップショット開始');
  
  var targetSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.TARGET_CHANNELS);
  var snapshotSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DAILY_SNAPSHOT);
  var data = targetSheet.getDataRange().getValues();
  
  var today = formatJST(new Date());
  var snapshots = [];
  
  for (var i = 1; i < data.length; i++) {
    var channelId = data[i][0];
    if (channelId) {
      try {
        var channelResponse = exponentialBackoff(function() {
          return YouTube.Channels.list('statistics', {
            id: channelId
          });
        });
        
        if (channelResponse.items && channelResponse.items.length > 0) {
          var stats = channelResponse.items[0].statistics;
          snapshots.push([
            today,
            channelId,
            parseInt(stats.subscriberCount) || 0,
            parseInt(stats.viewCount) || 0,
            parseInt(stats.videoCount) || 0
          ]);
        }
        
        Utilities.sleep(500);
      } catch (error) {
        logMessage('スナップショットエラー', 'ERROR', 'チャンネルID: ' + channelId);
      }
    }
  }
  
  // スナップショットデータを追加
  if (snapshots.length > 0) {
    snapshotSheet.getRange(snapshotSheet.getLastRow() + 1, 1, snapshots.length, 5).setValues(snapshots);
  }
  
  logMessage('日次スナップショット完了: ' + snapshots.length + '件');
}

// =============================================================================
// ダッシュボード・グラフ生成
// =============================================================================

function seedDashboard() {
  logMessage('ダッシュボード初期化開始');
  
  var dashSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DASHBOARD);
  
  // 基本統計の更新
  updateDashboardStats();
  
  // 既存グラフを削除
  var charts = dashSheet.getCharts();
  for (var i = 0; i < charts.length; i++) {
    dashSheet.removeChart(charts[i]);
  }
  
  // 4つのグラフを生成
  createSubscribersChart();
  createVPDChart();
  createTrendChart();
  createHeatmapChart();
  
  logMessage('ダッシュボード初期化完了');
  SpreadsheetApp.getUi().alert('完了', 'ダッシュボードのグラフを生成しました。', SpreadsheetApp.getUi().ButtonSet.OK);
}

function regenerateDashboard() {
  seedDashboard();
}

function updateDashboardStats() {
  var dashSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DASHBOARD);
  var discoveredSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  var targetSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.TARGET_CHANNELS);
  
  var discoveredData = discoveredSheet.getDataRange().getValues();
  var targetData = targetSheet.getDataRange().getValues();
  
  var totalDiscovered = discoveredData.length - 1; // ヘッダー除く
  var totalTarget = targetData.length - 1;
  
  var avgSubscribers = 0;
  if (totalDiscovered > 0) {
    var totalSubs = 0;
    for (var i = 1; i < discoveredData.length; i++) {
      totalSubs += parseInt(discoveredData[i][3]) || 0;
    }
    avgSubscribers = Math.round(totalSubs / totalDiscovered);
  }
  
  // 統計値を更新
  dashSheet.getRange(2, 2).setValue(formatJST(new Date()));
  dashSheet.getRange(3, 2).setValue(totalDiscovered);
  dashSheet.getRange(4, 2).setValue(totalTarget);
  dashSheet.getRange(5, 2).setValue(avgSubscribers);
}

function createSubscribersChart() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var discoveredSheet = ss.getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  var dashSheet = ss.getSheetByName(SHEET_NAMES.DASHBOARD);
  
  var data = discoveredSheet.getDataRange().getValues();
  if (data.length <= 1) return;
  
  // 上位20チャンネルを取得
  var channels = [];
  for (var i = 1; i < Math.min(21, data.length); i++) {
    channels.push([data[i][1], parseInt(data[i][3]) || 0]); // チャンネル名、登録者数
  }
  
  // 登録者数でソート
  channels.sort(function(a, b) { return b[1] - a[1]; });
  
  var chart = dashSheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(discoveredSheet.getRange(1, 2, Math.min(21, data.length), 1)) // チャンネル名
    .addRange(discoveredSheet.getRange(1, 4, Math.min(21, data.length), 1)) // 登録者数
    .setPosition(10, 1, 0, 0)
    .setOption('title', '上位20チャンネル 登録者数')
    .setOption('hAxis', {title: 'チャンネル'})
    .setOption('vAxis', {title: '登録者数'})
    .setOption('width', 600)
    .setOption('height', 300)
    .build();
  
  dashSheet.insertChart(chart);
}

function createVPDChart() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var discoveredSheet = ss.getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
  var dashSheet = ss.getSheetByName(SHEET_NAMES.DASHBOARD);
  
  var data = discoveredSheet.getDataRange().getValues();
  if (data.length <= 1) return;
  
  // VPD（動画あたり再生数）を計算
  var channels = [];
  for (var i = 1; i < Math.min(21, data.length); i++) {
    var viewCount = parseInt(data[i][4]) || 0;
    var videoCount = parseInt(data[i][5]) || 1;
    var vpd = Math.round(viewCount / videoCount);
    channels.push([data[i][1], vpd]);
  }
  
  // VPDでソート
  channels.sort(function(a, b) { return b[1] - a[1]; });
  
  var chart = dashSheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .setPosition(10, 8, 0, 0)
    .setOption('title', '上位20チャンネル 動画あたり再生数')
    .setOption('hAxis', {title: 'チャンネル'})
    .setOption('vAxis', {title: 'VPD'})
    .setOption('width', 600)
    .setOption('height', 300)
    .build();
  
  dashSheet.insertChart(chart);
}

function createTrendChart() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var snapshotSheet = ss.getSheetByName(SHEET_NAMES.DAILY_SNAPSHOT);
  var dashSheet = ss.getSheetByName(SHEET_NAMES.DASHBOARD);
  
  var data = snapshotSheet.getDataRange().getValues();
  if (data.length <= 1) return;
  
  var chart = dashSheet.newChart()
    .setChartType(Charts.ChartType.LINE)
    .addRange(snapshotSheet.getRange(1, 1, data.length, 3)) // 日付、チャンネルID、登録者数
    .setPosition(25, 1, 0, 0)
    .setOption('title', '分析対象チャンネル 登録者推移')
    .setOption('hAxis', {title: '日付'})
    .setOption('vAxis', {title: '登録者数'})
    .setOption('width', 600)
    .setOption('height', 300)
    .build();
  
  dashSheet.insertChart(chart);
}

function createHeatmapChart() {
  // 簡易的なヒートマップ風チャート（実際のヒートマップは制限あり）
  var dashSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DASHBOARD);
  
  // 曜日×時間帯の投稿頻度を仮想データで作成（実装時は実データを使用）
  var heatmapData = [
    ['時間帯', '月', '火', '水', '木', '金', '土', '日'],
    ['6-9時', 2, 3, 2, 4, 5, 8, 6],
    ['9-12時', 5, 6, 7, 5, 4, 3, 2],
    ['12-15時', 8, 7, 6, 8, 9, 5, 4],
    ['15-18時', 12, 11, 10, 12, 13, 8, 7],
    ['18-21時', 18, 19, 20, 18, 17, 15, 12],
    ['21-24時', 22, 21, 19, 21, 20, 18, 16]
  ];
  
  // データを一時的にシートに書き込み
  var tempRange = dashSheet.getRange(40, 1, heatmapData.length, heatmapData[0].length);
  tempRange.setValues(heatmapData);
  
  var chart = dashSheet.newChart()
    .setChartType(Charts.ChartType.TABLE)
    .addRange(tempRange)
    .setPosition(25, 8, 0, 0)
    .setOption('title', '投稿時間帯分析（曜日×時間）')
    .setOption('width', 600)
    .setOption('height', 300)
    .build();
  
  dashSheet.insertChart(chart);
}

// =============================================================================
// AI機能（自然言語Q&A）
// =============================================================================

function ASK_AI(prompt, range) {
  try {
    var settings = getSettings();
    var apiKey = settings.ANTHROPIC_API_KEY || settings.OPENAI_API_KEY;
    
    if (!apiKey) {
      return 'エラー: API キーが設定されていません。設定シートでANTHROPIC_API_KEYまたはOPENAI_API_KEYを設定してください。';
    }
    
    var data = '';
    if (range) {
      // 範囲が指定されている場合はその内容を取得
      var values = range.getValues();
      data = JSON.stringify(values);
    } else {
      // 範囲未指定の場合は発見チャンネルの概要を取得
      var discoveredSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
      var discoveredData = discoveredSheet.getDataRange().getValues();
      data = JSON.stringify(discoveredData.slice(0, 10)); // 上位10件のみ
    }
    
    var systemPrompt = 'あなたはYouTubeチャンネル分析の専門家です。提供されたデータを分析し、日本語で簡潔かつ有用な回答をしてください。';
    var fullPrompt = prompt + '\n\nデータ: ' + data.substring(0, 2000); // APIの制限を考慮
    
    if (settings.ANTHROPIC_API_KEY) {
      return callClaudeAPI(apiKey, systemPrompt, fullPrompt);
    } else {
      return callOpenAIAPI(apiKey, systemPrompt, fullPrompt);
    }
    
  } catch (error) {
    return 'AI処理エラー: ' + error.toString();
  }
}

function callClaudeAPI(apiKey, systemPrompt, prompt) {
  var url = 'https://api.anthropic.com/v1/messages';
  
  var payload = {
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 500,
    system: systemPrompt,
    messages: [
      {
        role: 'user',
        content: prompt
      }
    ]
  };
  
  var options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify(payload)
  };
  
  var response = UrlFetchApp.fetch(url, options);
  var result = JSON.parse(response.getContentText());
  
  if (result.content && result.content[0]) {
    return result.content[0].text;
  } else {
    return 'Claude APIエラー: ' + response.getContentText();
  }
}

function callOpenAIAPI(apiKey, systemPrompt, prompt) {
  var url = 'https://api.openai.com/v1/chat/completions';
  
  var payload = {
    model: 'gpt-3.5-turbo',
    messages: [
      {
        role: 'system',
        content: systemPrompt
      },
      {
        role: 'user',
        content: prompt
      }
    ],
    max_tokens: 500
  };
  
  var options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + apiKey
    },
    payload: JSON.stringify(payload)
  };
  
  var response = UrlFetchApp.fetch(url, options);
  var result = JSON.parse(response.getContentText());
  
  if (result.choices && result.choices[0]) {
    return result.choices[0].message.content;
  } else {
    return 'OpenAI APIエラー: ' + response.getContentText();
  }
}

function generateAISummary() {
  try {
    var settings = getSettings();
    if (!settings.ANTHROPIC_API_KEY && !settings.OPENAI_API_KEY) {
      SpreadsheetApp.getUi().alert('エラー', 'API キーが設定されていません。', SpreadsheetApp.getUi().ButtonSet.OK);
      return;
    }
    
    var dashSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DASHBOARD);
    var discoveredSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.DISCOVERED_CHANNELS);
    
    var prompt = '発見されたFX関連YouTubeチャンネルの主要なトレンドや特徴を3-4行で要約してください。登録者数、投稿頻度、人気動画の傾向などに注目してください。';
    var summary = ASK_AI(prompt, discoveredSheet.getDataRange());
    
    // ダッシュボードに要約を書き込み
    dashSheet.getRange(8, 2).setValue(summary);
    
    SpreadsheetApp.getUi().alert('完了', 'AI要約を生成しました。ダッシュボードをご確認ください。', SpreadsheetApp.getUi().ButtonSet.OK);
    logMessage('AI要約生成完了');
    
  } catch (error) {
    logMessage('AI要約エラー', 'ERROR', error.toString());
    SpreadsheetApp.getUi().alert('エラー', 'AI要約の生成に失敗しました: ' + error.toString(), SpreadsheetApp.getUi().ButtonSet.OK);
  }
}

// =============================================================================
// ユーティリティ関数
// =============================================================================

function exponentialBackoff(func, maxRetries) {
  maxRetries = maxRetries || 5;
  
  for (var i = 0; i < maxRetries; i++) {
    try {
      return func();
    } catch (error) {
      if (i === maxRetries - 1) {
        throw error;
      }
      
      var waitTime = Math.pow(2, i) * 1000 + Math.random() * 1000;
      Utilities.sleep(waitTime);
      logMessage('API呼び出しリトライ', 'WARN', 'Retry ' + (i + 1) + '/' + maxRetries);
    }
  }
}

function formatJST(dateString) {
  var date = new Date(dateString);
  return Utilities.formatDate(date, 'JST', 'yyyy-MM-dd HH:mm:ss');
}

function logMessage(message, level, details) {
  level = level || 'INFO';
  var logSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_NAMES.LOG);
  var timestamp = formatJST(new Date());
  
  logSheet.appendRow([timestamp, level, message, details || '']);
  
  // ログが1000行を超えた場合は古いものを削除
  if (logSheet.getLastRow() > 1000) {
    logSheet.deleteRows(2, 100); // 古い100行を削除
  }
  
  console.log('[' + timestamp + '] ' + level + ': ' + message);
}

// =============================================================================
// トリガー設定（手動で設定する必要があります）
// =============================================================================

function setupTriggers() {
  // 既存のトリガーを削除
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    ScriptApp.deleteTrigger(triggers[i]);
  }
  
  // 日次実行トリガー（メトリクス更新）
  ScriptApp.newTrigger('snapshotPublicMetrics')
    .timeBased()
    .everyDays(1)
    .atHour(9)
    .create();
  
  // 週次実行トリガー（競合発見）
  ScriptApp.newTrigger('discoverChannels')
    .timeBased()
    .everyWeeks(1)
    .onWeekDay(ScriptApp.WeekDay.MONDAY)
    .atHour(10)
    .create();
    
  logMessage('トリガー設定完了');
}