/**
 * YouTube チャンネル分析ツール - 日本FX特化統合版
 * Google Apps Script + YouTube Data API v3
 * 
 * 主な機能：
 * - 日本のFX関連YouTubeチャンネル自動発見（1000人以上限定）
 * - チャンネル・動画・コメント分析
 * - 自動ダッシュボード生成（グラフ付き）
 * - AI質問機能（Claude/OpenAI対応）
 * - 簡易モード（UI簡素化）
 */

// =============================================================================
// 設定とスキーマ定義
// =============================================================================

const CONFIG = {
  YOUTUBE_API_KEY: '', // ScriptPropertiesから取得
  SHEET_NAMES: {
    SEARCH_TERMS: '検索語',
    CHANNELS: 'チャンネル分析',
    VIDEOS: '動画分析', 
    COMMENTS: 'コメント分析',
    DASHBOARD: 'ダッシュボード',
    SETTINGS: '設定',
    LOG: 'ログ'
  },
  TARGET_CHANNELS: [],
  API_LIMITS: {
    REQUESTS_PER_MINUTE: 50,
    REQUESTS_PER_DAY: 10000,
    RETRY_ATTEMPTS: 3,
    BACKOFF_MULTIPLIER: 2,
    INITIAL_BACKOFF: 1000
  },
  ANALYSIS: {
    MAX_CHANNELS: 500,
    MAX_VIDEOS_PER_CHANNEL: 50,
    MAX_COMMENTS_PER_VIDEO: 100,
    MIN_SUBSCRIBERS: 1000,
    FX_RELEVANCE_THRESHOLD: 2,
    REGION_CODE: 'JP',
    RELEVANCE_LANGUAGE: 'ja'
  }
};

const COLUMN_SCHEMAS = {
  CHANNELS: [
    'チャンネルID', 'チャンネル名', 'チャンネルURL', 'チャンネル説明', 
    '登録者数', '総動画数', '総再生回数', '平均再生回数', 
    'チャンネル作成日', '国', 'FX関連度', '検証済み', '分析日時'
  ],
  VIDEOS: [
    'チャンネルID', 'チャンネル名', '動画ID', '動画タイトル', '動画URL',
    '公開日', '再生回数', 'いいね数', 'コメント数', '動画時間',
    'FX関連度', '感情スコア', 'キーワード', '分析日時'
  ],
  COMMENTS: [
    '動画ID', '動画タイトル', 'コメントID', '投稿者', 'コメント内容',
    'いいね数', '投稿日時', 'FX関連度', '感情スコア', 'キーワード'
  ]
};

const FX_KEYWORDS = [
  // 基本用語
  'FX', '為替', 'ドル円', 'USDJPY', 'EURJPY', 'GBPJPY', 'ポンド円',
  // 取引手法
  'トレード', 'スキャルピング', 'スキャル', 'デイトレード', 'デイトレ', 
  'スイングトレード', 'ポジショントレード',
  // テクニカル分析
  'テクニカル分析', 'チャート分析', '移動平均線', '移動平均', 'RSI', 'MACD',
  'ボリンジャーバンド', 'ボリンジャー', 'フィボナッチ', 'フィボ',
  'サポートライン', 'レジスタンスライン', 'サポレジ',
  // 概念・理論
  'プライスアクション', 'ダウ理論', 'エリオット波動',
  '経済指標', 'ファンダメンタル分析', 'ファンダメンタルズ',
  // 実務用語
  'ロング', 'ショート', 'エントリー', 'エグジット', 'ストップロス',
  'テイクプロフィット', 'レバレッジ', '証拠金', 'スプレッド', 'スワップ',
  'pips', 'ピップス', '通貨ペア', '外国為替'
];

const SIMPLE_MODE_SHEETS = [
  '検索語', 'チャンネル分析', '動画分析', 'ダッシュボード', '設定', 'ログ'
];

// =============================================================================
// メニュー作成
// =============================================================================

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('🎯 YouTube分析 (日本FX特化)')
    .addItem('🛠 初期セットアップ', 'initialSetup')
    .addSeparator()
    .addItem('🔎 日本のFXチャンネル発見（1000人以上）', 'discoverFxChannels')
    .addSeparator()
    .addItem('▶️ 全て実行', 'runAllAnalysis')
    .addItem('📺 チャンネル分析のみ', 'runChannelAnalysis')
    .addItem('🎬 動画分析のみ', 'runVideoAnalysis')
    .addItem('💬 コメント分析のみ', 'runCommentAnalysis')
    .addItem('📊 ダッシュボード更新', 'updateDashboard')
    .addSeparator()
    .addItem('🤖 ダッシュボード要約（AI）', 'generateAiSummary')
    .addItem('🧭 簡易モード ON/OFF', 'toggleSimpleMode')
    .addSeparator()
    .addItem('🔧 設定', 'openSettings')
    .addItem('🗂 シート管理', 'openDeletionManager')
    .addItem('❓ ヘルプ', 'showHelp')
    .create();
}

// =============================================================================
// 初期セットアップ
// =============================================================================

function initialSetup() {
  try {
    log('初期セットアップを開始します...');
    
    // 必要なシートを作成
    createRequiredSheets();
    
    // 初期設定値をセット
    setupInitialSettings();
    
    // 初期検索語をセット
    setupInitialSearchTerms();
    
    log('初期セットアップが完了しました');
    showSuccess('初期セットアップ完了', 
      '必要なシートと初期設定が作成されました。\n' +
      '次に「🔧 設定」からYouTube API キーを設定してください。');
  } catch (error) {
    log(`初期セットアップエラー: ${error.toString()}`);
    showError('セットアップエラー', error.toString());
  }
}

function createRequiredSheets() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheetNames = Object.values(CONFIG.SHEET_NAMES);
  
  // 検索語シート
  const searchTermsSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.SEARCH_TERMS);
  if (searchTermsSheet.getLastRow() <= 1) {
    searchTermsSheet.getRange(1, 1, 1, 2).setValues([['検索語', '説明']]);
  }
  
  // メインシート作成
  getOrCreateSheet(CONFIG.SHEET_NAMES.CHANNELS, COLUMN_SCHEMAS.CHANNELS);
  getOrCreateSheet(CONFIG.SHEET_NAMES.VIDEOS, COLUMN_SCHEMAS.VIDEOS);
  getOrCreateSheet(CONFIG.SHEET_NAMES.COMMENTS, COLUMN_SCHEMAS.COMMENTS);
  
  // ダッシュボードシート
  const dashboardSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.DASHBOARD);
  if (dashboardSheet.getLastRow() <= 1) {
    dashboardSheet.getRange(1, 1, 1, 3).setValues([['項目', '値', '備考']]);
  }
  
  // 設定シート
  const settingsSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.SETTINGS);
  if (settingsSheet.getLastRow() <= 1) {
    settingsSheet.getRange(1, 1, 1, 3).setValues([['設定項目', '値', '説明']]);
  }
  
  // ログシート
  const logSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.LOG);
  if (logSheet.getLastRow() <= 1) {
    logSheet.getRange(1, 1, 1, 2).setValues([['日時', 'メッセージ']]);
  }
}

function setupInitialSettings() {
  const settingsSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.SETTINGS);
  const initialSettings = [
    ['MAX_SEARCH', '500', '最大発見チャンネル数'],
    ['MIN_SUBSCRIBERS', '1000', '最小登録者数フィルター'],
    ['REGION_CODE', 'JP', '検索地域コード'],
    ['LANG', 'ja', '検索言語'],
    ['FX_THRESHOLD', '2', 'FX関連度しきい値'],
    ['SIMPLE_MODE', 'OFF', '簡易モード（ON/OFF）'],
    ['ANTHROPIC_API_KEY', '', 'Claude API キー（AI機能用）'],
    ['OPENAI_API_KEY', '', 'OpenAI API キー（AI機能用）']
  ];
  
  if (settingsSheet.getLastRow() <= 1) {
    settingsSheet.getRange(2, 1, initialSettings.length, 3).setValues(initialSettings);
  }
}

function setupInitialSearchTerms() {
  const searchSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.SEARCH_TERMS);
  const initialTerms = FX_KEYWORDS.slice(0, 15).map(keyword => [keyword, 'FX関連キーワード']);
  
  if (searchSheet.getLastRow() <= 1) {
    searchSheet.getRange(2, 1, initialTerms.length, 2).setValues(initialTerms);
  }
}

// =============================================================================
// チャンネル発見機能 - async 関数として修正
// =============================================================================

async function discoverFxChannels() {
  try {
    log('日本FXチャンネル発見を開始します...');
    showProgress('チャンネル発見中', '日本のFX関連チャンネルを検索しています...');
    
    const searchTerms = getSearchTerms();
    const maxChannels = parseInt(getSetting('MAX_SEARCH') || CONFIG.ANALYSIS.MAX_CHANNELS);
    const minSubscribers = parseInt(getSetting('MIN_SUBSCRIBERS') || CONFIG.ANALYSIS.MIN_SUBSCRIBERS);
    
    let discoveredChannels = new Map();
    let processedCount = 0;
    
    for (const term of searchTerms) {
      if (processedCount >= maxChannels) break;
      
      log(`検索実行: "${term}"`);
      const channels = await searchChannelsByTerm(term, Math.min(50, maxChannels - processedCount));
      
      for (const [channelId, channelData] of channels.entries()) {
        if (!discoveredChannels.has(channelId) && processedCount < maxChannels) {
          // 登録者数フィルター
          if (channelData.subscriberCount >= minSubscribers) {
            // FX関連度チェック
            const fxRelevance = await calculateFxRelevanceForDiscovery(channelData);
            const threshold = parseFloat(getSetting('FX_THRESHOLD') || CONFIG.ANALYSIS.FX_RELEVANCE_THRESHOLD);
            
            if (fxRelevance >= threshold) {
              channelData.fxRelevance = fxRelevance;
              discoveredChannels.set(channelId, channelData);
              processedCount++;
            }
          }
        }
      }
      
      // API制限を考慮した待機
      Utilities.sleep(1000);
    }
    
    // チャンネル分析シートに書き込み
    await writeDiscoveredChannels(discoveredChannels);
    
    log(`チャンネル発見完了: ${discoveredChannels.size}件`);
    showSuccess('発見完了', `${discoveredChannels.size}件のFX関連チャンネルを発見しました。`);
    
  } catch (error) {
    log(`チャンネル発見エラー: ${error.toString()}`);
    showError('発見エラー', error.toString());
  }
}

async function searchChannelsByTerm(searchTerm, maxResults) {
  const channels = new Map();
  let nextPageToken = '';
  let totalFetched = 0;
  
  while (totalFetched < maxResults && nextPageToken !== null) {
    try {
      // チャンネル検索
      const searchResponse = await makeApiRequest('search', {
        part: 'snippet',
        q: searchTerm,
        type: 'channel',
        regionCode: CONFIG.ANALYSIS.REGION_CODE,
        relevanceLanguage: CONFIG.ANALYSIS.RELEVANCE_LANGUAGE,
        maxResults: Math.min(50, maxResults - totalFetched),
        pageToken: nextPageToken || undefined
      });
      
      if (!searchResponse.items || searchResponse.items.length === 0) break;
      
      // チャンネルID収集
      const channelIds = searchResponse.items.map(item => item.snippet.channelId);
      
      // チャンネル詳細取得
      const detailsResponse = await makeApiRequest('channels', {
        part: 'snippet,statistics,contentDetails',
        id: channelIds.join(',')
      });
      
      // データ処理
      if (detailsResponse.items) {
        for (const channel of detailsResponse.items) {
          const subscriberCount = parseInt(channel.statistics.subscriberCount) || 0;
          const viewCount = parseInt(channel.statistics.viewCount) || 0;
          const videoCount = parseInt(channel.statistics.videoCount) || 0;
          
          // 基本フィルター（非公開・0・異常値の除外）
          if (subscriberCount > 0 && !isNaN(subscriberCount)) {
            channels.set(channel.id, {
              id: channel.id,
              title: channel.snippet.title,
              description: channel.snippet.description || '',
              customUrl: channel.snippet.customUrl || '',
              country: channel.snippet.country || 'JP',
              subscriberCount: subscriberCount,
              videoCount: videoCount,
              viewCount: viewCount,
              publishedAt: channel.snippet.publishedAt,
              thumbnails: channel.snippet.thumbnails
            });
          }
        }
      }
      
      totalFetched += searchResponse.items.length;
      nextPageToken = searchResponse.nextPageToken || null;
      
    } catch (error) {
      log(`検索エラー (${searchTerm}): ${error.toString()}`);
      break;
    }
  }
  
  return channels;
}

async function calculateFxRelevanceForDiscovery(channelData) {
  let score = 0;
  const text = `${channelData.title} ${channelData.description}`.toLowerCase();
  
  // FXキーワードマッチング
  for (const keyword of FX_KEYWORDS) {
    const matches = text.split(keyword.toLowerCase()).length - 1;
    score += matches;
  }
  
  // 日本語判定加点
  if (/[ぁ-んァ-ン一-龥]/.test(channelData.title)) {
    score += 1;
  }
  
  // 英語主体の減点
  const englishRatio = (text.match(/[a-z]/g) || []).length / text.length;
  if (englishRatio > 0.7) {
    score -= 2;
  }
  
  // 最新動画タイトルからの加点（可能であれば）
  try {
    const recentVideos = await getChannelRecentVideos(channelData.id, 5);
    for (const video of recentVideos) {
      const videoText = video.title.toLowerCase();
      for (const keyword of FX_KEYWORDS) {
        if (videoText.includes(keyword.toLowerCase())) {
          score += 0.5;
        }
      }
    }
  } catch (error) {
    // 動画取得エラーは無視（チャンネル情報のみでスコアリング）
  }
  
  return Math.max(0, score);
}

async function getChannelRecentVideos(channelId, maxResults = 5) {
  try {
    const response = await makeApiRequest('search', {
      part: 'snippet',
      channelId: channelId,
      type: 'video',
      order: 'date',
      maxResults: maxResults
    });
    
    return response.items || [];
  } catch (error) {
    return [];
  }
}

function getSearchTerms() {
  const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.SEARCH_TERMS);
  const data = sheet.getDataRange().getValues();
  const terms = [];
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][0]) {
      terms.push(data[i][0]);
    }
  }
  
  return terms.length > 0 ? terms : FX_KEYWORDS.slice(0, 10);
}

async function writeDiscoveredChannels(channelsMap) {
  const sheet = getOrCreateSheet(CONFIG.SHEET_NAMES.CHANNELS, COLUMN_SCHEMAS.CHANNELS);
  
  // 既存データをクリア（ヘッダーは保持）
  if (sheet.getLastRow() > 1) {
    sheet.deleteRows(2, sheet.getLastRow() - 1);
  }
  
  const rows = [];
  const now = new Date();
  
  for (const [channelId, channel] of channelsMap.entries()) {
    const channelUrl = generateChannelUrl(channel);
    const averageViews = channel.videoCount > 0 ? Math.round(channel.viewCount / channel.videoCount) : 0;
    const verified = channel.subscriberCount >= CONFIG.ANALYSIS.MIN_SUBSCRIBERS ? 'はい' : 'いいえ';
    
    rows.push([
      channel.id,                              // チャンネルID
      channel.title,                           // チャンネル名
      channelUrl,                              // チャンネルURL
      truncateText(channel.description, 200),  // チャンネル説明
      channel.subscriberCount,                 // 登録者数
      channel.videoCount,                      // 総動画数
      channel.viewCount,                       // 総再生回数
      averageViews,                            // 平均再生回数
      formatDate(channel.publishedAt),         // チャンネル作成日
      channel.country,                         // 国
      channel.fxRelevance || 0,                // FX関連度
      verified,                                // 検証済み
      formatDate(now)                          // 分析日時
    ]);
  }
  
  if (rows.length > 0) {
    sheet.getRange(2, 1, rows.length, COLUMN_SCHEMAS.CHANNELS.length).setValues(rows);
    formatSheet(sheet, COLUMN_SCHEMAS.CHANNELS);
  }
}

function generateChannelUrl(channel) {
  if (channel.customUrl) {
    return `https://www.youtube.com/@${channel.customUrl}`;
  } else {
    return `https://www.youtube.com/channel/${channel.id}`;
  }
}

// =============================================================================
// 既存の分析機能（統合版ベース）
// =============================================================================

async function runAllAnalysis() {
  try {
    showProgress('全体分析開始', '全ての分析を実行しています...');
    log('全体分析を開始します');
    
    await runChannelAnalysis();
    await runVideoAnalysis();
    await runCommentAnalysis();
    await updateDashboard();
    
    log('全体分析が完了しました');
    showSuccess('分析完了', '全ての分析が完了しました。ダッシュボードをご確認ください。');
  } catch (error) {
    log(`全体分析エラー: ${error.toString()}`);
    showError('分析エラー', error.toString());
  }
}

async function runChannelAnalysis() {
  try {
    log('チャンネル分析を開始します');
    const channels = getTargetChannels();
    
    if (channels.length === 0) {
      showError('エラー', 'チャンネルが設定されていません。先にチャンネル発見を実行してください。');
      return;
    }
    
    const sheet = getOrCreateSheet(CONFIG.SHEET_NAMES.CHANNELS, COLUMN_SCHEMAS.CHANNELS);
    
    for (let i = 0; i < channels.length; i++) {
      const channelId = channels[i];
      log(`チャンネル分析中: ${channelId} (${i + 1}/${channels.length})`);
      
      const channelInfo = await getChannelInfo(channelId);
      if (channelInfo) {
        const analysis = await analyzeChannel(channelInfo);
        updateChannelSheet(sheet, analysis, i + 2);
      }
      
      // API制限対策
      if (i > 0 && i % 10 === 0) {
        Utilities.sleep(2000);
      }
    }
    
    formatSheet(sheet, COLUMN_SCHEMAS.CHANNELS);
    log('チャンネル分析が完了しました');
  } catch (error) {
    log(`チャンネル分析エラー: ${error.toString()}`);
    throw error;
  }
}

async function runVideoAnalysis() {
  try {
    log('動画分析を開始します');
    const channels = getTargetChannels();
    
    if (channels.length === 0) {
      showError('エラー', 'チャンネルが設定されていません。');
      return;
    }
    
    const sheet = getOrCreateSheet(CONFIG.SHEET_NAMES.VIDEOS, COLUMN_SCHEMAS.VIDEOS);
    sheet.clear();
    sheet.getRange(1, 1, 1, COLUMN_SCHEMAS.VIDEOS.length).setValues([COLUMN_SCHEMAS.VIDEOS]);
    
    let rowIndex = 2;
    
    for (const channelId of channels) {
      log(`動画分析中: ${channelId}`);
      
      const channelInfo = await getChannelInfo(channelId);
      if (!channelInfo) continue;
      
      const videos = await getChannelVideos(channelId);
      
      for (const video of videos) {
        const analysis = await analyzeVideo(video, channelInfo);
        updateVideoSheet(sheet, analysis, rowIndex);
        rowIndex++;
        
        // API制限対策
        Utilities.sleep(500);
      }
    }
    
    formatSheet(sheet, COLUMN_SCHEMAS.VIDEOS);
    log('動画分析が完了しました');
  } catch (error) {
    log(`動画分析エラー: ${error.toString()}`);
    throw error;
  }
}

async function runCommentAnalysis() {
  try {
    log('コメント分析を開始します');
    const videosSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.VIDEOS);
    
    if (!videosSheet || videosSheet.getLastRow() <= 1) {
      showError('エラー', '先に動画分析を実行してください。');
      return;
    }
    
    const videoData = videosSheet.getDataRange().getValues();
    const commentsSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.COMMENTS, COLUMN_SCHEMAS.COMMENTS);
    commentsSheet.clear();
    commentsSheet.getRange(1, 1, 1, COLUMN_SCHEMAS.COMMENTS.length).setValues([COLUMN_SCHEMAS.COMMENTS]);
    
    let rowIndex = 2;
    
    for (let i = 1; i < videoData.length; i++) {
      const videoId = videoData[i][2];
      const videoTitle = videoData[i][3];
      
      log(`コメント分析中: ${videoTitle}`);
      
      try {
        const comments = await getVideoComments(videoId);
        
        for (const comment of comments) {
          const analysis = await analyzeComments([comment]);
          updateCommentSheet(commentsSheet, {
            videoId: videoId,
            videoTitle: videoTitle,
            ...comment,
            ...analysis
          }, rowIndex);
          rowIndex++;
        }
      } catch (error) {
        log(`コメント取得エラー (${videoId}): ${error.toString()}`);
        continue;
      }
      
      // API制限対策
      Utilities.sleep(1000);
    }
    
    formatSheet(commentsSheet, COLUMN_SCHEMAS.COMMENTS);
    log('コメント分析が完了しました');
  } catch (error) {
    log(`コメント分析エラー: ${error.toString()}`);
    throw error;
  }
}

// =============================================================================
// API関連機能
// =============================================================================

async function getChannelInfo(channelId) {
  try {
    const response = await makeApiRequest('channels', {
      part: 'snippet,statistics,contentDetails',
      id: channelId
    });
    
    if (response.items && response.items.length > 0) {
      return response.items[0];
    }
    return null;
  } catch (error) {
    log(`チャンネル情報取得エラー: ${error.toString()}`);
    return null;
  }
}

async function getChannelVideos(channelId) {
  try {
    const videos = [];
    let nextPageToken = '';
    let totalFetched = 0;
    const maxVideos = CONFIG.ANALYSIS.MAX_VIDEOS_PER_CHANNEL;
    
    while (totalFetched < maxVideos && nextPageToken !== null) {
      const searchResponse = await makeApiRequest('search', {
        part: 'snippet',
        channelId: channelId,
        type: 'video',
        order: 'date',
        maxResults: Math.min(50, maxVideos - totalFetched),
        pageToken: nextPageToken || undefined
      });
      
      if (!searchResponse.items) break;
      
      const videoIds = searchResponse.items.map(item => item.id.videoId);
      const detailsResponse = await makeApiRequest('videos', {
        part: 'snippet,statistics,contentDetails',
        id: videoIds.join(',')
      });
      
      if (detailsResponse.items) {
        videos.push(...detailsResponse.items);
      }
      
      totalFetched += searchResponse.items.length;
      nextPageToken = searchResponse.nextPageToken || null;
    }
    
    return videos;
  } catch (error) {
    log(`動画取得エラー: ${error.toString()}`);
    return [];
  }
}

async function getVideoDetails(videoId) {
  try {
    const response = await makeApiRequest('videos', {
      part: 'snippet,statistics,contentDetails',
      id: videoId
    });
    
    if (response.items && response.items.length > 0) {
      return response.items[0];
    }
    return null;
  } catch (error) {
    log(`動画詳細取得エラー: ${error.toString()}`);
    return null;
  }
}

async function getVideoComments(videoId, maxComments = null) {
  try {
    const comments = [];
    let nextPageToken = '';
    let totalFetched = 0;
    const maxLimit = maxComments || CONFIG.ANALYSIS.MAX_COMMENTS_PER_VIDEO;
    
    while (totalFetched < maxLimit && nextPageToken !== null) {
      const response = await makeApiRequest('commentThreads', {
        part: 'snippet',
        videoId: videoId,
        maxResults: Math.min(100, maxLimit - totalFetched),
        order: 'relevance',
        pageToken: nextPageToken || undefined
      });
      
      if (!response.items) break;
      
      for (const item of response.items) {
        const comment = item.snippet.topLevelComment.snippet;
        comments.push({
          id: item.id,
          author: comment.authorDisplayName,
          text: comment.textDisplay,
          likeCount: comment.likeCount || 0,
          publishedAt: comment.publishedAt
        });
      }
      
      totalFetched += response.items.length;
      nextPageToken = response.nextPageToken || null;
    }
    
    return comments;
  } catch (error) {
    log(`コメント取得エラー: ${error.toString()}`);
    return [];
  }
}

async function makeApiRequest(endpoint, params) {
  const apiKey = PropertiesService.getScriptProperties().getProperty('YOUTUBE_API_KEY');
  if (!apiKey) {
    throw new Error('YouTube API キーが設定されていません');
  }
  
  const baseUrl = 'https://www.googleapis.com/youtube/v3/';
  let url = `${baseUrl}${endpoint}?key=${apiKey}`;
  
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      url += `&${key}=${encodeURIComponent(value)}`;
    }
  }
  
  for (let attempt = 1; attempt <= CONFIG.API_LIMITS.RETRY_ATTEMPTS; attempt++) {
    try {
      const response = UrlFetchApp.fetch(url);
      recordApiUsage();
      
      if (response.getResponseCode() === 200) {
        return JSON.parse(response.getContentText());
      } else if (response.getResponseCode() === 429) {
        // レート制限
        const waitTime = CONFIG.API_LIMITS.INITIAL_BACKOFF * Math.pow(CONFIG.API_LIMITS.BACKOFF_MULTIPLIER, attempt - 1);
        log(`APIレート制限、待機中: ${waitTime}ms`);
        Utilities.sleep(waitTime);
        continue;
      } else {
        throw new Error(`API エラー: ${response.getResponseCode()}`);
      }
    } catch (error) {
      if (attempt === CONFIG.API_LIMITS.RETRY_ATTEMPTS) {
        throw error;
      }
      const waitTime = CONFIG.API_LIMITS.INITIAL_BACKOFF * Math.pow(CONFIG.API_LIMITS.BACKOFF_MULTIPLIER, attempt - 1);
      Utilities.sleep(waitTime);
    }
  }
}

// =============================================================================
// 分析機能
// =============================================================================

async function analyzeChannel(channelInfo) {
  const stats = channelInfo.statistics || {};
  const snippet = channelInfo.snippet || {};
  
  const subscriberCount = parseInt(stats.subscriberCount) || 0;
  const videoCount = parseInt(stats.videoCount) || 0;
  const viewCount = parseInt(stats.viewCount) || 0;
  const averageViews = videoCount > 0 ? Math.round(viewCount / videoCount) : 0;
  
  const fxRelevance = calculateFxRelevance(snippet.title, snippet.description);
  const channelUrl = generateChannelUrl({
    customUrl: snippet.customUrl,
    id: channelInfo.id
  });
  const verified = subscriberCount >= CONFIG.ANALYSIS.MIN_SUBSCRIBERS ? 'はい' : 'いいえ';
  
  return {
    id: channelInfo.id,
    title: snippet.title || '',
    url: channelUrl,
    description: snippet.description || '',
    subscriberCount: subscriberCount,
    videoCount: videoCount,
    viewCount: viewCount,
    averageViews: averageViews,
    publishedAt: snippet.publishedAt,
    country: snippet.country || '',
    fxRelevance: fxRelevance,
    verified: verified,
    analyzedAt: new Date()
  };
}

async function analyzeVideo(videoInfo, channelInfo) {
  const stats = videoInfo.statistics || {};
  const snippet = videoInfo.snippet || {};
  
  const fxRelevance = calculateFxRelevance(snippet.title, snippet.description);
  const sentiment = calculateSentiment(snippet.title + ' ' + (snippet.description || ''));
  const keywords = extractKeywords(snippet.title + ' ' + (snippet.description || ''));
  
  return {
    channelId: videoInfo.snippet.channelId,
    channelTitle: channelInfo ? channelInfo.snippet.title : '',
    videoId: videoInfo.id,
    title: snippet.title || '',
    url: `https://www.youtube.com/watch?v=${videoInfo.id}`,
    publishedAt: snippet.publishedAt,
    viewCount: parseInt(stats.viewCount) || 0,
    likeCount: parseInt(stats.likeCount) || 0,
    commentCount: parseInt(stats.commentCount) || 0,
    duration: parseYouTubeDuration(videoInfo.contentDetails?.duration || ''),
    fxRelevance: fxRelevance,
    sentiment: sentiment,
    keywords: keywords.join(', '),
    analyzedAt: new Date()
  };
}

async function analyzeComments(comments) {
  let totalSentiment = 0;
  let fxMentions = 0;
  const allKeywords = [];
  
  for (const comment of comments) {
    const text = comment.text || '';
    const sentiment = calculateSentiment(text);
    totalSentiment += sentiment;
    
    if (isFxRelated(text)) {
      fxMentions++;
    }
    
    const keywords = extractKeywords(text);
    allKeywords.push(...keywords);
  }
  
  const avgSentiment = comments.length > 0 ? totalSentiment / comments.length : 0;
  const fxRelevance = comments.length > 0 ? (fxMentions / comments.length) * 10 : 0;
  const topKeywords = [...new Set(allKeywords)].slice(0, 10);
  
  return {
    sentiment: Math.round(avgSentiment * 100) / 100,
    fxRelevance: Math.round(fxRelevance * 100) / 100,
    keywords: topKeywords.join(', ')
  };
}

function calculateFxRelevance(title, description) {
  const text = `${title} ${description}`.toLowerCase();
  let score = 0;
  
  for (const keyword of FX_KEYWORDS) {
    const matches = text.split(keyword.toLowerCase()).length - 1;
    score += matches;
  }
  
  // 日本語判定加点
  if (/[ぁ-んァ-ン一-龥]/.test(title)) {
    score += 1;
  }
  
  return Math.min(10, score);
}

function calculateSentiment(text) {
  // 簡易感情分析（ポジティブ・ネガティブキーワードベース）
  const positiveWords = ['良い', 'すごい', '素晴らしい', '最高', '勝利', '利益', '成功'];
  const negativeWords = ['悪い', 'だめ', 'ひどい', '最悪', '損失', '負け', '失敗'];
  
  const lowerText = text.toLowerCase();
  let score = 0;
  
  for (const word of positiveWords) {
    score += (lowerText.split(word).length - 1);
  }
  
  for (const word of negativeWords) {
    score -= (lowerText.split(word).length - 1);
  }
  
  return Math.max(-5, Math.min(5, score));
}

function extractKeywords(text) {
  const words = text.toLowerCase().match(/[a-zA-Zぁ-んァ-ン一-龥]+/g) || [];
  const wordCount = {};
  
  for (const word of words) {
    if (word.length > 2) {
      wordCount[word] = (wordCount[word] || 0) + 1;
    }
  }
  
  return Object.entries(wordCount)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([word]) => word);
}

function checkFxRelevance(text) {
  return calculateFxRelevance(text, '') > 0;
}

function detectLanguage(text) {
  if (/[ぁ-んァ-ン一-龥]/.test(text)) return 'ja';
  if (/[a-zA-Z]/.test(text)) return 'en';
  return 'unknown';
}

function isFxRelated(text) {
  const lowerText = text.toLowerCase();
  return FX_KEYWORDS.some(keyword => lowerText.includes(keyword.toLowerCase()));
}

function parseYouTubeDuration(duration) {
  const match = duration.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  if (!match) return '00:00';
  
  const hours = parseInt(match[1]) || 0;
  const minutes = parseInt(match[2]) || 0;
  const seconds = parseInt(match[3]) || 0;
  
  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  } else {
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }
}

// =============================================================================
// シート操作
// =============================================================================

function getOrCreateSheet(sheetName, headers = null) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = ss.getSheetByName(sheetName);
  
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
    if (headers) {
      sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
      formatSheet(sheet, headers);
    }
  }
  
  return sheet;
}

function updateChannelSheet(sheet, analysis, rowIndex) {
  const row = [
    analysis.id,
    analysis.title,
    analysis.url,
    truncateText(analysis.description, 200),
    analysis.subscriberCount,
    analysis.videoCount,
    analysis.viewCount,
    analysis.averageViews,
    formatDate(analysis.publishedAt),
    analysis.country,
    analysis.fxRelevance,
    analysis.verified,
    formatDate(analysis.analyzedAt)
  ];
  
  sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
}

function updateVideoSheet(sheet, analysis, rowIndex) {
  const row = [
    analysis.channelId,
    analysis.channelTitle,
    analysis.videoId,
    analysis.title,
    analysis.url,
    formatDate(analysis.publishedAt),
    analysis.viewCount,
    analysis.likeCount,
    analysis.commentCount,
    analysis.duration,
    analysis.fxRelevance,
    analysis.sentiment,
    analysis.keywords,
    formatDate(analysis.analyzedAt)
  ];
  
  sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
}

function updateCommentSheet(sheet, data, rowIndex) {
  const row = [
    data.videoId,
    data.videoTitle,
    data.id,
    data.author,
    truncateText(data.text, 500),
    data.likeCount,
    formatDate(data.publishedAt),
    data.fxRelevance,
    data.sentiment,
    data.keywords
  ];
  
  sheet.getRange(rowIndex, 1, 1, row.length).setValues([row]);
}

function formatSheet(sheet, headers) {
  const headerRow = sheet.getRange(1, 1, 1, headers.length);
  headerRow.setBackground('#4285f4');
  headerRow.setFontColor('white');
  headerRow.setFontWeight('bold');
  
  // 列幅の自動調整
  for (let i = 1; i <= headers.length; i++) {
    sheet.autoResizeColumn(i);
  }
}

// =============================================================================
// ダッシュボード機能
// =============================================================================

async function updateDashboard() {
  try {
    log('ダッシュボード更新を開始します');
    const dashboardSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.DASHBOARD);
    
    // 既存のグラフを削除
    const charts = dashboardSheet.getCharts();
    for (const chart of charts) {
      dashboardSheet.removeChart(chart);
    }
    
    // 統計情報の更新
    await updateDashboardStats(dashboardSheet);
    
    // グラフの生成
    await createSubscriberChart(dashboardSheet);
    await createAverageViewChart(dashboardSheet);
    await createTopVideosChart(dashboardSheet);
    
    log('ダッシュボード更新が完了しました');
  } catch (error) {
    log(`ダッシュボード更新エラー: ${error.toString()}`);
    throw error;
  }
}

async function updateDashboardStats(dashboardSheet) {
  const channelsSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.CHANNELS);
  const videosSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.VIDEOS);
  
  const stats = [];
  
  // 基本統計
  stats.push(['最終更新', formatDate(new Date()), '']);
  
  if (channelsSheet && channelsSheet.getLastRow() > 1) {
    const channelData = channelsSheet.getDataRange().getValues();
    const channelCount = channelData.length - 1;
    
    let totalSubscribers = 0;
    let totalViews = 0;
    
    for (let i = 1; i < channelData.length; i++) {
      totalSubscribers += parseInt(channelData[i][4]) || 0;
      totalViews += parseInt(channelData[i][6]) || 0;
    }
    
    stats.push(['分析チャンネル数', channelCount, '件']);
    stats.push(['総登録者数', totalSubscribers.toLocaleString(), '人']);
    stats.push(['平均登録者数', Math.round(totalSubscribers / channelCount).toLocaleString(), '人']);
    stats.push(['総再生回数', totalViews.toLocaleString(), '回']);
  }
  
  if (videosSheet && videosSheet.getLastRow() > 1) {
    const videoData = videosSheet.getDataRange().getValues();
    const videoCount = videoData.length - 1;
    
    let totalVideoViews = 0;
    for (let i = 1; i < videoData.length; i++) {
      totalVideoViews += parseInt(videoData[i][6]) || 0;
    }
    
    stats.push(['分析動画数', videoCount, '本']);
    stats.push(['動画平均再生数', Math.round(totalVideoViews / videoCount).toLocaleString(), '回']);
  }
  
  // 統計データの書き込み
  if (stats.length > 0) {
    dashboardSheet.getRange(1, 1, stats.length, 3).setValues(stats);
  }
}

async function createSubscriberChart(dashboardSheet) {
  const channelsSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.CHANNELS);
  if (!channelsSheet || channelsSheet.getLastRow() <= 1) return;
  
  const data = channelsSheet.getDataRange().getValues();
  
  // 登録者数でソートして上位20件を取得
  const channelData = data.slice(1).sort((a, b) => (parseInt(b[4]) || 0) - (parseInt(a[4]) || 0)).slice(0, 20);
  
  if (channelData.length === 0) return;
  
  // チャート用のデータ範囲を作成
  const chartData = [['チャンネル名', '登録者数']];
  for (const row of channelData) {
    chartData.push([row[1], parseInt(row[4]) || 0]);
  }
  
  // 一時的なデータ範囲を作成
  const startRow = Math.max(20, dashboardSheet.getLastRow() + 2);
  const dataRange = dashboardSheet.getRange(startRow, 1, chartData.length, 2);
  dataRange.setValues(chartData);
  
  // チャート作成
  const chart = dashboardSheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(dataRange)
    .setPosition(1, 5, 0, 0)
    .setOption('title', '上位20チャンネル - 登録者数')
    .setOption('hAxis', { title: 'チャンネル', titleTextStyle: { color: '#333' } })
    .setOption('vAxis', { title: '登録者数', titleTextStyle: { color: '#333' } })
    .setOption('width', 600)
    .setOption('height', 400)
    .build();
  
  dashboardSheet.insertChart(chart);
}

async function createAverageViewChart(dashboardSheet) {
  const channelsSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.CHANNELS);
  if (!channelsSheet || channelsSheet.getLastRow() <= 1) return;
  
  const data = channelsSheet.getDataRange().getValues();
  
  // 平均再生回数でソートして上位20件を取得
  const channelData = data.slice(1).sort((a, b) => (parseInt(b[7]) || 0) - (parseInt(a[7]) || 0)).slice(0, 20);
  
  if (channelData.length === 0) return;
  
  // チャート用のデータ範囲を作成
  const chartData = [['チャンネル名', '平均再生回数']];
  for (const row of channelData) {
    chartData.push([row[1], parseInt(row[7]) || 0]);
  }
  
  // 一時的なデータ範囲を作成
  const startRow = Math.max(45, dashboardSheet.getLastRow() + 2);
  const dataRange = dashboardSheet.getRange(startRow, 1, chartData.length, 2);
  dataRange.setValues(chartData);
  
  // チャート作成
  const chart = dashboardSheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(dataRange)
    .setPosition(1, 13, 0, 0)
    .setOption('title', '上位20チャンネル - 平均再生回数')
    .setOption('hAxis', { title: 'チャンネル', titleTextStyle: { color: '#333' } })
    .setOption('vAxis', { title: '平均再生回数', titleTextStyle: { color: '#333' } })
    .setOption('width', 600)
    .setOption('height', 400)
    .build();
  
  dashboardSheet.insertChart(chart);
}

async function createTopVideosChart(dashboardSheet) {
  const videosSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.VIDEOS);
  if (!videosSheet || videosSheet.getLastRow() <= 1) return;
  
  const data = videosSheet.getDataRange().getValues();
  
  // 再生回数でソートして上位20件を取得
  const videoData = data.slice(1).sort((a, b) => (parseInt(b[6]) || 0) - (parseInt(a[6]) || 0)).slice(0, 20);
  
  if (videoData.length === 0) return;
  
  // チャート用のデータ範囲を作成
  const chartData = [['動画タイトル', '再生回数']];
  for (const row of videoData) {
    chartData.push([truncateText(row[3], 30), parseInt(row[6]) || 0]);
  }
  
  // 一時的なデータ範囲を作成
  const startRow = Math.max(70, dashboardSheet.getLastRow() + 2);
  const dataRange = dashboardSheet.getRange(startRow, 1, chartData.length, 2);
  dataRange.setValues(chartData);
  
  // チャート作成
  const chart = dashboardSheet.newChart()
    .setChartType(Charts.ChartType.COLUMN)
    .addRange(dataRange)
    .setPosition(25, 5, 0, 0)
    .setOption('title', '上位20動画 - 再生回数')
    .setOption('hAxis', { title: '動画タイトル', titleTextStyle: { color: '#333' } })
    .setOption('vAxis', { title: '再生回数', titleTextStyle: { color: '#333' } })
    .setOption('width', 600)
    .setOption('height', 400)
    .build();
  
  dashboardSheet.insertChart(chart);
}

// =============================================================================
// AI機能
// =============================================================================

function ASK_AI(prompt, range) {
  try {
    const anthropicKey = getSetting('ANTHROPIC_API_KEY');
    const openaiKey = getSetting('OPENAI_API_KEY');
    
    if (!anthropicKey && !openaiKey) {
      return 'エラー: AI APIキーが設定されていません。設定シートでAPIキーを設定してください。';
    }
    
    let data = '';
    if (range) {
      const values = range.getValues();
      data = summarizeRangeData(values);
    } else {
      data = getDashboardSummary();
    }
    
    if (anthropicKey) {
      return callClaudeAPI(anthropicKey, prompt, data);
    } else {
      return callOpenAIAPI(openaiKey, prompt, data);
    }
    
  } catch (error) {
    return `AI処理エラー: ${error.toString()}`;
  }
}

function summarizeRangeData(values) {
  if (!values || values.length === 0) return 'データが見つかりません';
  
  const headers = values[0];
  const dataRows = values.slice(1);
  
  let summary = `データ概要:\n`;
  summary += `- 総行数: ${dataRows.length}件\n`;
  summary += `- 列: ${headers.join(', ')}\n\n`;
  
  // 数値列の統計
  for (let col = 0; col < headers.length; col++) {
    const columnName = headers[col];
    const numericValues = dataRows
      .map(row => parseFloat(row[col]))
      .filter(val => !isNaN(val));
    
    if (numericValues.length > 0) {
      const total = numericValues.reduce((sum, val) => sum + val, 0);
      const avg = total / numericValues.length;
      const max = Math.max(...numericValues);
      const min = Math.min(...numericValues);
      
      summary += `${columnName}: 合計=${total.toLocaleString()}, 平均=${Math.round(avg).toLocaleString()}, 最大=${max.toLocaleString()}, 最小=${min.toLocaleString()}\n`;
    }
  }
  
  return summary;
}

function getDashboardSummary() {
  const dashboardSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.DASHBOARD);
  if (!dashboardSheet) return 'ダッシュボードデータが見つかりません';
  
  const data = dashboardSheet.getDataRange().getValues();
  let summary = 'ダッシュボード情報:\n';
  
  for (const row of data) {
    if (row[0] && row[1]) {
      summary += `${row[0]}: ${row[1]}\n`;
    }
  }
  
  return summary;
}

function callClaudeAPI(apiKey, prompt, data) {
  const url = 'https://api.anthropic.com/v1/messages';
  
  const payload = {
    model: 'claude-3-5-sonnet-20241022',
    max_tokens: 1000,
    system: 'あなたはYouTubeチャンネル分析の専門家です。提供されたデータを分析し、日本語で簡潔で有用な洞察を提供してください。',
    messages: [
      {
        role: 'user',
        content: `${prompt}\n\nデータ:\n${data}`
      }
    ]
  };
  
  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    payload: JSON.stringify(payload)
  };
  
  const response = UrlFetchApp.fetch(url, options);
  const result = JSON.parse(response.getContentText());
  
  if (result.content && result.content[0]) {
    return result.content[0].text;
  } else {
    return 'Claude APIエラー: ' + response.getContentText();
  }
}

function callOpenAIAPI(apiKey, prompt, data) {
  const url = 'https://api.openai.com/v1/chat/completions';
  
  const payload = {
    model: 'gpt-4',
    messages: [
      {
        role: 'system',
        content: 'あなたはYouTubeチャンネル分析の専門家です。提供されたデータを分析し、日本語で簡潔で有用な洞察を提供してください。'
      },
      {
        role: 'user',
        content: `${prompt}\n\nデータ:\n${data}`
      }
    ],
    max_tokens: 1000,
    temperature: 0.7
  };
  
  const options = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + apiKey
    },
    payload: JSON.stringify(payload)
  };
  
  const response = UrlFetchApp.fetch(url, options);
  const result = JSON.parse(response.getContentText());
  
  if (result.choices && result.choices[0]) {
    return result.choices[0].message.content;
  } else {
    return 'OpenAI APIエラー: ' + response.getContentText();
  }
}

function generateAiSummary() {
  try {
    const summary = ASK_AI('この分析結果の主要なトレンドと注目すべきチャンネルの特徴を要約してください。特に登録者数、再生数、FX関連度の観点から分析してください。');
    
    const dashboardSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.DASHBOARD);
    const summaryRow = dashboardSheet.getLastRow() + 2;
    
    dashboardSheet.getRange(summaryRow, 1, 1, 3).setValues([['AI要約', summary, '']]);
    dashboardSheet.getRange(summaryRow, 1, 1, 3).setBackground('#e8f5e8');
    
    log('AI要約を生成しました');
    showSuccess('AI要約完了', 'ダッシュボードにAI要約を追加しました。');
  } catch (error) {
    log(`AI要約エラー: ${error.toString()}`);
    showError('AI要約エラー', error.toString());
  }
}

// =============================================================================
// 簡易モード機能
// =============================================================================

function toggleSimpleMode() {
  const currentMode = getSetting('SIMPLE_MODE') || 'OFF';
  const newMode = currentMode === 'ON' ? 'OFF' : 'ON';
  
  setSetting('SIMPLE_MODE', newMode);
  
  if (newMode === 'ON') {
    enableSimpleMode();
  } else {
    disableSimpleMode();
  }
  
  showSuccess('モード切替', `簡易モードを${newMode}にしました。`);
  log(`簡易モード切替: ${newMode}`);
}

function enableSimpleMode() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  
  for (const sheet of sheets) {
    const sheetName = sheet.getName();
    if (SIMPLE_MODE_SHEETS.includes(sheetName)) {
      sheet.showSheet();
    } else {
      sheet.hideSheet();
    }
  }
}

function disableSimpleMode() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  
  for (const sheet of sheets) {
    sheet.showSheet();
  }
}

// =============================================================================
// 設定・ユーティリティ
// =============================================================================

function setYouTubeApiKey() {
  const ui = SpreadsheetApp.getUi();
  const response = ui.prompt('API キー設定', 'YouTube Data API v3 のAPIキーを入力してください:', ui.ButtonSet.OK_CANCEL);
  
  if (response.getSelectedButton() === ui.Button.OK) {
    const apiKey = response.getResponseText().trim();
    if (apiKey) {
      PropertiesService.getScriptProperties().setProperty('YOUTUBE_API_KEY', apiKey);
      ui.alert('設定完了', 'APIキーが保存されました。', ui.ButtonSet.OK);
      log('YouTube APIキーを設定しました');
    }
  }
}

function getTargetChannels() {
  // チャンネル分析シートからチャンネルIDを取得
  const channelsSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.CHANNELS);
  if (!channelsSheet || channelsSheet.getLastRow() <= 1) {
    return [];
  }
  
  const data = channelsSheet.getDataRange().getValues();
  const channelIds = [];
  
  for (let i = 1; i < data.length; i++) {
    if (data[i][0]) {
      channelIds.push(data[i][0]);
    }
  }
  
  return channelIds;
}

function getSetting(key) {
  const settingsSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(CONFIG.SHEET_NAMES.SETTINGS);
  if (!settingsSheet) return null;
  
  const data = settingsSheet.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === key) {
      return data[i][1];
    }
  }
  return null;
}

function setSetting(key, value) {
  const settingsSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.SETTINGS);
  const data = settingsSheet.getDataRange().getValues();
  
  // 既存設定の更新
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === key) {
      settingsSheet.getRange(i + 1, 2).setValue(value);
      return;
    }
  }
  
  // 新規設定の追加
  settingsSheet.appendRow([key, value, '']);
}

function recordApiUsage() {
  const today = new Date().toDateString();
  const currentUsage = parseInt(PropertiesService.getScriptProperties().getProperty(`API_USAGE_${today}`) || '0');
  PropertiesService.getScriptProperties().setProperty(`API_USAGE_${today}`, (currentUsage + 1).toString());
}

function checkApiQuota() {
  const today = new Date().toDateString();
  const usage = parseInt(PropertiesService.getScriptProperties().getProperty(`API_USAGE_${today}`) || '0');
  return usage < CONFIG.API_LIMITS.REQUESTS_PER_DAY;
}

// =============================================================================
// UI機能
// =============================================================================

function showProgress(title, message) {
  if (isInteractive()) {
    const ui = SpreadsheetApp.getUi();
    // 進行状況はログで代用（UIでの進行表示は制限あり）
    log(`${title}: ${message}`);
  }
}

function showSuccess(title, message) {
  if (isInteractive()) {
    SpreadsheetApp.getUi().alert(title, message, SpreadsheetApp.getUi().ButtonSet.OK);
  }
  log(`成功 - ${title}: ${message}`);
}

function showError(title, message) {
  if (isInteractive()) {
    SpreadsheetApp.getUi().alert(title, message, SpreadsheetApp.getUi().ButtonSet.OK);
  }
  log(`エラー - ${title}: ${message}`);
}

function isInteractive() {
  try {
    SpreadsheetApp.getActiveSpreadsheet();
    return true;
  } catch (e) {
    return false;
  }
}

function openSettings() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('設定メニュー')
    .addItem('YouTube API キー設定', 'setYouTubeApiKey')
    .addItem('設定シートを開く', 'openSettingsSheet')
    .create();
    
  // 設定シートを開く
  openSettingsSheet();
}

function openSettingsSheet() {
  const settingsSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.SETTINGS);
  SpreadsheetApp.setActiveSheet(settingsSheet);
}

function openDeletionManager() {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheets = ss.getSheets();
  
  let sheetList = 'シート一覧:\n';
  sheets.forEach((sheet, index) => {
    sheetList += `${index + 1}. ${sheet.getName()}\n`;
  });
  
  const response = ui.prompt('シート管理', 
    sheetList + '\n削除するシート名を入力してください（慎重に！）:', 
    ui.ButtonSet.OK_CANCEL);
    
  if (response.getSelectedButton() === ui.Button.OK) {
    const sheetName = response.getResponseText().trim();
    if (sheetName) {
      deleteSheet(sheetName);
    }
  }
}

function deleteSheet(sheetName) {
  const ui = SpreadsheetApp.getUi();
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);
  
  if (sheet) {
    const confirmResponse = ui.alert('確認', 
      `シート「${sheetName}」を削除しますか？この操作は取り消せません。`, 
      ui.ButtonSet.YES_NO);
      
    if (confirmResponse === ui.Button.YES) {
      ss.deleteSheet(sheet);
      log(`シート削除: ${sheetName}`);
      ui.alert('完了', `シート「${sheetName}」を削除しました。`, ui.ButtonSet.OK);
    }
  } else {
    ui.alert('エラー', `シート「${sheetName}」が見つかりません。`, ui.ButtonSet.OK);
  }
}

function showHelp() {
  const helpText = `
🎯 YouTube分析ツール (日本FX特化) - ヘルプ

■ 基本的な使い方：
1. 「🛠 初期セットアップ」で必要なシートを作成
2. 「🔧 設定」からYouTube API キーを設定
3. 「🔎 日本のFXチャンネル発見」でFX関連チャンネルを自動発見
4. 「▶️ 全て実行」で包括的な分析を実行
5. 「📊 ダッシュボード更新」でグラフ付きレポートを生成

■ 個別機能：
- 📺 チャンネル分析のみ：チャンネル詳細を分析
- 🎬 動画分析のみ：動画の詳細データを取得・分析  
- 💬 コメント分析のみ：コメントの感情分析・キーワード抽出
- 🤖 ダッシュボード要約（AI）：AI による分析結果の要約
- 🧭 簡易モード ON/OFF：表示するシートを制限

■ AI機能の使い方：
1. 設定シートでANTHROPIC_API_KEYまたはOPENAI_API_KEYを設定
2. セルに =ASK_AI("質問内容") または =ASK_AI("質問内容", 範囲) と入力
3. 例：=ASK_AI("上位チャンネルの特徴は？", チャンネル分析!A1:M20)

■ 注意事項：
- YouTube Data API の1日の制限は10,000リクエストです
- 大量のデータ処理には時間がかかります
- コメント分析は動画でコメントが有効な場合のみ実行されます

■ トラブルシューティング：
- APIエラー：キーの設定とクォータ残量を確認
- データが取得されない：チャンネルIDや動画IDを確認
- AI機能が動作しない：APIキーの設定を確認
`;

  SpreadsheetApp.getUi().alert('ヘルプ', helpText, SpreadsheetApp.getUi().ButtonSet.OK);
}

// =============================================================================
// 補助関数
// =============================================================================

function truncateText(text, maxLength) {
  if (!text) return '';
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
}

function formatDate(date) {
  if (!date) return '';
  if (typeof date === 'string') {
    date = new Date(date);
  }
  return Utilities.formatDate(date, Session.getScriptTimeZone(), 'yyyy-MM-dd HH:mm:ss');
}

function log(message) {
  const timestamp = formatDate(new Date());
  console.log(`[${timestamp}] ${message}`);
  
  // ログシートにも記録
  try {
    const logSheet = getOrCreateSheet(CONFIG.SHEET_NAMES.LOG);
    logSheet.appendRow([timestamp, message]);
    
    // ログが1000行を超えた場合は古いものを削除
    if (logSheet.getLastRow() > 1000) {
      logSheet.deleteRows(2, 100);
    }
  } catch (error) {
    console.error('ログ記録エラー:', error);
  }
}