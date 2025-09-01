# テスト手順書 - FX YouTube 分析ツール（堅牢版）

## 🧪 テスト概要

このドキュメントでは、堅牢版FXチャンネル分析ツールの各機能をテストする手順を説明します。

## 📋 テスト環境の準備

### 1. テスト用スプレッドシートの作成

1. 新しいGoogle Sheetsを作成
2. 名前を「FXチャンネル分析テスト」に変更
3. `analysegas_robust.gs`をApps Scriptに配置
4. `ai-assistant.html`をHTMLファイルとして追加

### 2. テスト用APIキーの設定

```
スクリプトプロパティ:
- YOUTUBE_API_KEY: [テスト用APIキー]
```

**⚠️ 注意**: 本番環境とは別のAPIキーを使用することを推奨

## 🏷️ テストカテゴリ

### A. 基本機能テスト
- [A1. 初期設定テスト](#a1-初期設定テスト)
- [A2. メニュー表示テスト](#a2-メニュー表示テスト)
- [A3. シート作成テスト](#a3-シート作成テスト)

### B. クォータ管理テスト
- [B1. DRY_RUNテスト](#b1-dry_runテスト)
- [B2. FORCE_LOW_BUDGETテスト](#b2-force_low_budgetテスト)
- [B3. クォータ計算テスト](#b3-クォータ計算テスト)

### C. API呼び出しテスト
- [C1. 正常系API呼び出しテスト](#c1-正常系api呼び出しテスト)
- [C2. エラーハンドリングテスト](#c2-エラーハンドリングテスト)
- [C3. レート制限テスト](#c3-レート制限テスト)

### D. データ処理テスト
- [D1. チャンネル探索テスト](#d1-チャンネル探索テスト)
- [D2. バッチ処理テスト](#d2-バッチ処理テスト)
- [D3. 差分更新テスト](#d3-差分更新テスト)

### E. 統合テスト
- [E1. 全自動実行テスト](#e1-全自動実行テスト)
- [E2. 定期実行テスト](#e2-定期実行テスト)
- [E3. パフォーマンステスト](#e3-パフォーマンステスト)

---

## A. 基本機能テスト

### A1. 初期設定テスト

**目的**: 初期設定が正常に動作することを確認

**手順**:
1. スプレッドシートを開く
2. メニューが表示されることを確認
3. 「📋 初期設定」を実行
4. 権限承認ダイアログで「承認」をクリック
5. 完了メッセージが表示されることを確認

**期待結果**:
- [x] メニューに「🎯 競合分析（堅牢版）」が表示される
- [x] 初期設定完了のメッセージが表示される
- [x] 以下のシートが作成される：
  - 検索語
  - 設定
  - クォータ管理
  - その他すべてのシート

**検証**:
```javascript
function testInitialization() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const requiredSheets = Object.values(SHEET_NAMES);
  
  requiredSheets.forEach(sheetName => {
    const sheet = ss.getSheetByName(sheetName);
    console.log(`${sheetName}: ${sheet ? '✅ 存在' : '❌ 不存在'}`);
  });
}
```

### A2. メニュー表示テスト

**目的**: メニューが正しく表示されることを確認

**手順**:
1. スプレッドシートをリロード
2. メニューバーを確認

**期待結果**:
- [x] 「🎯 競合分析（堅牢版）」メニューが表示される
- [x] サブメニューが正しく表示される
- [x] 各メニュー項目がクリック可能

### A3. シート作成テスト

**目的**: 各シートが正しいフォーマットで作成されることを確認

**手順**:
1. 各シートを開いて内容を確認
2. ヘッダーの書式を確認
3. 初期データの確認

**期待結果**:
- [x] 検索語シート: FX関連キーワードが設定済み
- [x] 設定シート: デフォルト設定値が設定済み
- [x] ヘッダーが青色で書式設定済み
- [x] フリーズペインが設定済み

---

## B. クォータ管理テスト

### B1. DRY_RUNテスト

**目的**: DRY_RUNモードでAPIを呼ばずに動作確認

**手順**:
1. コード内でCONFIGを変更:
   ```javascript
   const CONFIG = {
     DRY_RUN: true,  // API呼び出しをスキップ
     // ...
   };
   ```
2. 保存後、「今すぐ 全自動実行」を実行
3. ログを確認

**期待結果**:
- [x] `[DRY_RUN] API呼び出し:` メッセージがログに出力される
- [x] `[DRY_RUN] クォータ消費:` メッセージがログに出力される
- [x] 実際のAPIは呼ばれない
- [x] モックデータで処理が継続される
- [x] クォータが実際には消費されない

**検証コード**:
```javascript
function testDryRun() {
  const client = new YouTubeApiClient();
  const result = client.callApi('search', {q: 'test'}, 100);
  
  console.log('DRY_RUN結果:', result);
  console.log('モックデータかどうか:', result.items[0].snippet.title === 'Mock FX Channel');
}
```

### B2. FORCE_LOW_BUDGETテスト

**目的**: クォータ不足時の動作確認

**手順**:
1. CONFIGを変更:
   ```javascript
   const CONFIG = {
     FORCE_LOW_BUDGET: true,  // 擬似的に残量200に設定
     // ...
   };
   ```
2. 保存後、「今すぐ 全自動実行」を実行
3. アラートメッセージを確認

**期待結果**:
- [x] 「⚠️ クォータ不足」のアラートが表示される
- [x] 探索処理がスキップされる
- [x] 更新処理のみ実行される（残量がある場合）
- [x] ログに「⚠️ クォータ制限: 更新のみ実行」が記録される

**検証コード**:
```javascript
function testLowBudget() {
  const guard = new QuotaBudgetGuard();
  const remaining = guard.getRemainingQuota();
  const canSearch = guard.canPerformSearch();
  
  console.log('残りクォータ:', remaining);
  console.log('探索可能:', canSearch);
  
  // 期待値: 200, false
}
```

### B3. クォータ計算テスト

**目的**: クォータの計算が正確であることを確認

**手順**:
1. 以下の関数を実行:
   ```javascript
   function testQuotaCalculation() {
     const guard = new QuotaBudgetGuard();
     
     // 初期状態を確認
     const initial = guard.getRemainingQuota();
     console.log('初期残量:', initial);
     
     // 100ユニット消費
     guard.consumeQuota(100);
     
     // 消費後を確認
     const afterConsume = guard.getRemainingQuota();
     console.log('消費後残量:', afterConsume);
     
     // 差分が100であることを確認
     console.log('消費量:', initial - afterConsume);
   }
   ```

**期待結果**:
- [x] 消費前後の差分が正確に100
- [x] PropertiesServiceに正しく保存される
- [x] 複数回実行で累積される

---

## C. API呼び出しテスト

### C1. 正常系API呼び出しテスト

**目的**: 正常なAPI呼び出しが動作することを確認

**手順**:
1. DRY_RUN = false に設定
2. 有効なAPIキーを設定
3. 以下の関数を実行:
   ```javascript
   function testValidApiCall() {
     const client = new YouTubeApiClient();
     
     try {
       const result = client.callApi('search', {
         part: 'snippet',
         type: 'channel',
         q: 'FX',
         maxResults: 1
       }, 100);
       
       console.log('API呼び出し成功:', result);
       console.log('チャンネル数:', result.items.length);
     } catch (error) {
       console.error('API呼び出しエラー:', error.message);
     }
   }
   ```

**期待結果**:
- [x] APIが正常に呼ばれる
- [x] レスポンスにitemsが含まれる
- [x] クォータが正しく消費される
- [x] エラーが発生しない

### C2. エラーハンドリングテスト

**目的**: 各種エラーが適切にハンドリングされることを確認

#### C2-1. 無効なAPIキーテスト

**手順**:
1. 無効なAPIキーを設定
2. API呼び出しを実行
3. エラーログを確認

**期待結果**:
- [x] 403エラーが発生する
- [x] エラーが適切にキャッチされる
- [x] 実行ログに記録される
- [x] プログラムが異常終了しない

#### C2-2. 存在しないチャンネルIDテスト

**手順**:
```javascript
function testInvalidChannelId() {
  const client = new YouTubeApiClient();
  
  try {
    const result = client.callApi('channels', {
      part: 'snippet',
      id: 'INVALID_CHANNEL_ID'
    }, 1);
    
    console.log('結果:', result);
  } catch (error) {
    console.log('エラーキャッチ:', error.message);
  }
}
```

**期待結果**:
- [x] 空のitemsが返される
- [x] エラーが発生しない
- [x] 適切に処理が継続される

### C3. レート制限テスト

**目的**: レート制限の処理が正しく動作することを確認

**手順**:
1. 短時間で複数のAPI呼び出しを実行
2. バックオフ動作を確認

**検証コード**:
```javascript
function testRateLimit() {
  const client = new YouTubeApiClient();
  
  // 連続してAPI呼び出し（意図的にレート制限を発生させる）
  for (let i = 0; i < 5; i++) {
    try {
      console.log(`API呼び出し ${i + 1}`);
      const result = client.callApi('search', {
        part: 'snippet',
        type: 'channel',
        q: 'FX test ' + i,
        maxResults: 1
      }, 100);
      
      console.log(`成功: ${result.items.length}件`);
      
    } catch (error) {
      console.log(`エラー: ${error.message}`);
      
      if (error.message.includes('rateLimitExceeded')) {
        console.log('レート制限エラーが正しく処理されました');
        break;
      }
    }
  }
}
```

**期待結果**:
- [x] レート制限エラーが発生する
- [x] 自動バックオフが動作する
- [x] 指数バックオフで遅延が増加する
- [x] 最大リトライ回数後に処理が停止する

---

## D. データ処理テスト

### D1. チャンネル探索テスト

**目的**: チャンネル探索機能が正しく動作することを確認

**手順**:
1. 検索語シートに「FXテスト」を追加
2. 「1. チャンネル探索」を実行
3. 発見チャンネルシートを確認

**期待結果**:
- [x] FX関連チャンネルが発見される
- [x] 登録者1,000人以上のチャンネルのみ抽出される
- [x] FxScoreが計算されている
- [x] チャンネルURLが正しく設定されている
- [x] 重複チャンネルがない

**検証コード**:
```javascript
function testChannelDiscovery() {
  const sheet = getOrCreateSheet(SHEET_NAMES.DISCOVERED);
  
  if (sheet.getLastRow() <= 1) {
    console.log('❌ チャンネルが発見されませんでした');
    return;
  }
  
  const data = sheet.getDataRange().getValues();
  console.log(`✅ ${data.length - 1}件のチャンネルを発見`);
  
  // データ品質チェック
  let validChannels = 0;
  for (let i = 1; i < data.length; i++) {
    const subscriberCount = data[i][3];
    const fxScore = data[i][9];
    const channelUrl = data[i][8];
    
    if (subscriberCount >= 1000 && fxScore >= 0 && channelUrl) {
      validChannels++;
    }
  }
  
  console.log(`✅ 有効なチャンネル: ${validChannels}/${data.length - 1}`);
}
```

### D2. バッチ処理テスト

**目的**: バッチ処理が効率的に動作することを確認

**手順**:
1. 多数のチャンネルIDを生成
2. バッチ処理を実行
3. 処理時間と結果を確認

**検証コード**:
```javascript
function testBatchProcessing() {
  const testChannelIds = [
    'UC4YaOt1yT-ZeyB0OmxHgolA', // 実際のチャンネルIDを使用
    'UCjYjjz_LOqWaADRhT1nzDPQ',
    'UCZf__ehlCEBPop-_sldpBUQ'
  ];
  
  const startTime = Date.now();
  
  const client = new YouTubeApiClient();
  const results = getChannelDetailsBatch(testChannelIds, client);
  
  const endTime = Date.now();
  
  console.log(`処理時間: ${endTime - startTime}ms`);
  console.log(`結果数: ${results.length}`);
  console.log(`平均処理時間: ${(endTime - startTime) / testChannelIds.length}ms/チャンネル`);
}
```

**期待結果**:
- [x] 複数のチャンネルが一度に処理される
- [x] 50件ずつのバッチで分割される
- [x] 個別処理より高速
- [x] エラーが発生してもバッチ全体が停止しない

### D3. 差分更新テスト

**目的**: 差分更新が正しく動作することを確認

**手順**:
1. 初回の動画収集を実行
2. 同じチャンネルで再度収集を実行
3. 新規動画のみが追加されることを確認

**検証コード**:
```javascript
function testIncrementalUpdate() {
  const videoSheet = getOrCreateSheet(SHEET_NAMES.VIDEOS);
  const initialCount = videoSheet.getLastRow() - 1;
  
  console.log(`初回動画数: ${initialCount}`);
  
  // 差分更新を実行
  fetchVideosBatch();
  
  const afterCount = videoSheet.getLastRow() - 1;
  console.log(`更新後動画数: ${afterCount}`);
  console.log(`新規追加: ${afterCount - initialCount}`);
  
  // 重複チェック
  const data = videoSheet.getDataRange().getValues();
  const videoIds = new Set();
  let duplicates = 0;
  
  for (let i = 1; i < data.length; i++) {
    const videoId = data[i][3];
    if (videoIds.has(videoId)) {
      duplicates++;
    } else {
      videoIds.add(videoId);
    }
  }
  
  console.log(`重複動画数: ${duplicates}`);
}
```

**期待結果**:
- [x] 既存の動画はスキップされる
- [x] 新規動画のみが追加される
- [x] 重複がない
- [x] 処理時間が短縮される

---

## E. 統合テスト

### E1. 全自動実行テスト

**目的**: 全体の処理フローが正しく動作することを確認

**手順**:
1. すべてのシートをクリア
2. 「今すぐ 全自動実行」を実行
3. 各段階の成功を確認

**期待結果**:
- [x] 探索からダッシュボード生成まで完了
- [x] 各シートにデータが設定される
- [x] エラーが発生しない
- [x] クォータが予算内に収まる
- [x] 実行時間が6分以内

**検証チェックリスト**:
- [ ] 検索語シート: FX関連キーワードが設定済み
- [ ] 発見チャンネル: 20件以上のチャンネル
- [ ] 分析対象チャンネル: 上位20件が選定済み
- [ ] 動画一覧: 各チャンネルの動画が収集済み
- [ ] チャンネルスコア: VPD、成長率が計算済み
- [ ] ダッシュボード: グラフとテーブルが作成済み
- [ ] クォータ管理: 使用量が記録済み

### E2. 定期実行テスト

**目的**: トリガーによる定期実行が正しく動作することを確認

**手順**:
1. トリガーを設定
2. 手動でトリガー関数を実行
3. ログを確認

**検証コード**:
```javascript
function testScheduledExecution() {
  // 週次探索のテスト
  console.log('=== 週次探索テスト ===');
  runWeeklyDiscovery();
  
  // 日次更新のテスト
  console.log('=== 日次更新テスト ===');
  runDailyUpdate();
  
  // キャッシュ確認
  const cache = CacheService.getScriptCache();
  const lastSearch = cache.get('LAST_SEARCH_DATE');
  console.log('最終探索日:', lastSearch);
}
```

**期待結果**:
- [x] 週次探索が正しく実行される
- [x] キャッシュが正しく更新される
- [x] 7日以内の再実行時はスキップされる
- [x] 日次更新が差分で実行される

### E3. パフォーマンステスト

**目的**: 大量データでの性能を確認

**手順**:
1. 大量の検索語（50件）を設定
2. 実行時間を測定
3. メモリ使用量を確認

**検証コード**:
```javascript
function testPerformance() {
  const startTime = Date.now();
  const startMemory = DriveApp.getStorageUsed(); // 概算
  
  // 大量実行
  runAutoAdaptive();
  
  const endTime = Date.now();
  const endMemory = DriveApp.getStorageUsed();
  
  console.log('=== パフォーマンス結果 ===');
  console.log(`実行時間: ${(endTime - startTime) / 1000}秒`);
  console.log(`メモリ増加: ${endMemory - startMemory}バイト`);
  
  // クォータ使用量チェック
  const guard = new QuotaBudgetGuard();
  const status = guard.logQuotaStatus();
  console.log(`クォータ使用: ${status.percentage}%`);
}
```

**期待結果**:
- [x] 実行時間が6分以内
- [x] クォータ使用量が予算内
- [x] メモリ不足エラーが発生しない
- [x] 大量データでも安定動作

---

## 🚨 異常系テスト

### エラー注入テスト

**目的**: 各種エラーシナリオでの動作確認

#### 1. ネットワークエラーテスト
```javascript
function testNetworkError() {
  // UrlFetchApp.fetchをモックして例外を発生させる
  const originalFetch = UrlFetchApp.fetch;
  
  UrlFetchApp.fetch = function() {
    throw new Error('DNS_ERROR');
  };
  
  try {
    const client = new YouTubeApiClient();
    client.callApi('search', {q: 'test'}, 100);
  } catch (error) {
    console.log('ネットワークエラーハンドリング:', error.message);
  } finally {
    // 復元
    UrlFetchApp.fetch = originalFetch;
  }
}
```

#### 2. 部分的なデータ破損テスト
```javascript
function testPartialDataCorruption() {
  const sheet = getOrCreateSheet(SHEET_NAMES.DISCOVERED);
  
  // 意図的に不正なデータを挿入
  sheet.getRange(2, 1, 1, 14).setValues([[
    '', // 空のチャンネルID
    'Test Channel',
    'Description',
    'invalid_number', // 無効な登録者数
    100000,
    50,
    'JP',
    '2023-01-01',
    'https://youtube.com/channel/test',
    50,
    'ja',
    '',
    '',
    new Date()
  ]]);
  
  // 処理を実行して例外処理を確認
  try {
    selectCompetitors();
    console.log('✅ 部分的なデータ破損に対処できました');
  } catch (error) {
    console.log('❌ データ破損でエラー:', error.message);
  }
}
```

---

## 📊 テスト結果の記録

### テスト実行記録テンプレート

```
=== テスト実行記録 ===
実行日時: [YYYY-MM-DD HH:mm:ss]
実行者: [名前]
バージョン: v3.0.0

【基本機能テスト】
A1. 初期設定: ✅ PASS / ❌ FAIL
A2. メニュー表示: ✅ PASS / ❌ FAIL  
A3. シート作成: ✅ PASS / ❌ FAIL

【クォータ管理テスト】
B1. DRY_RUN: ✅ PASS / ❌ FAIL
B2. FORCE_LOW_BUDGET: ✅ PASS / ❌ FAIL
B3. クォータ計算: ✅ PASS / ❌ FAIL

【API呼び出しテスト】
C1. 正常系API: ✅ PASS / ❌ FAIL
C2. エラーハンドリング: ✅ PASS / ❌ FAIL
C3. レート制限: ✅ PASS / ❌ FAIL

【データ処理テスト】
D1. チャンネル探索: ✅ PASS / ❌ FAIL
D2. バッチ処理: ✅ PASS / ❌ FAIL
D3. 差分更新: ✅ PASS / ❌ FAIL

【統合テスト】
E1. 全自動実行: ✅ PASS / ❌ FAIL
E2. 定期実行: ✅ PASS / ❌ FAIL
E3. パフォーマンス: ✅ PASS / ❌ FAIL

総合判定: ✅ PASS / ❌ FAIL
備考: [特記事項があれば記入]
```

### 継続的テストの推奨

1. **日次チェック**
   - クォータ使用量の確認
   - エラーログの確認

2. **週次チェック**  
   - パフォーマンステストの実行
   - データ品質の確認

3. **月次チェック**
   - 全テストスイートの実行
   - 異常系テストの実行

4. **リリース前**
   - 全テストケースの実行
   - 本番環境での動作確認

---

## 🔧 デバッグ用ツール

### ログレベル設定
```javascript
function enableDebugMode() {
  const CONFIG = {
    DEBUG_MODE: true,
    // ...
  };
  
  console.log('デバッグモードを有効にしました');
}
```

### クォータリセット（テスト用）
```javascript
function resetQuotaForTesting() {
  const properties = PropertiesService.getScriptProperties();
  const today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), 'yyyy-MM-dd');
  const quotaKey = `QUOTA_USED_${today}`;
  
  properties.deleteProperty(quotaKey);
  console.log('テスト用にクォータをリセットしました');
}
```

これらのテスト手順により、堅牢版FXチャンネル分析ツールの品質と信頼性を確保できます。