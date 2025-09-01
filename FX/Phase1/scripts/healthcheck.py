#!/usr/bin/env python3
"""
FX News System ヘルスチェック
必要なモジュールと環境変数の確認
"""

import os
import sys

def check_module_imports():
    """必要なモジュールのimport確認"""
    modules = [
        'requests',
        'feedparser', 
        'bs4',
        'readability',
        'langdetect',
        'tldextract',
        'dotenv'
    ]
    
    print("🔍 モジュール import 確認:")
    all_ok = True
    
    for module in modules:
        try:
            if module == 'bs4':
                from bs4 import BeautifulSoup
                print(f"  ✅ {module} (BeautifulSoup)")
            elif module == 'readability':
                from readability import Document
                print(f"  ✅ {module} (Document)")
            elif module == 'dotenv':
                from dotenv import load_dotenv
                print(f"  ✅ {module} (load_dotenv)")
            else:
                __import__(module)
                print(f"  ✅ {module}")
        except ImportError as e:
            print(f"  ❌ {module} - Error: {e}")
            all_ok = False
    
    return all_ok

def check_env_variables():
    """環境変数の確認（.envから読み込み）"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except:
        print("⚠️  python-dotenvが利用できません")
    
    print("\n🔧 環境変数確認:")
    
    # 必須とオプションの変数を分類
    required_vars = [
        ('DISCORD_WEBHOOK', 'Discord 基本Webhook', True),
        ('DISCORD_WEBHOOK_ALERTS', 'Discord アラートWebhook', False), 
        ('DISCORD_WEBHOOK_DIGEST', 'Discord ダイジェストWebhook', False)
    ]
    
    optional_vars = [
        ('OPENAI_API_KEY', 'OpenAI APIキー'),
        ('DEEPL_API_KEY', 'DeepL APIキー'),
        ('TIMEZONE', 'タイムゾーン設定')
    ]
    
    all_required_ok = True
    
    for var_name, description, is_critical in required_vars:
        value = os.environ.get(var_name)
        if value:
            # セキュリティのため一部をマスク
            masked_value = value[:20] + "..." + value[-10:] if len(value) > 30 else value[:10] + "..."
            print(f"  ✅ {var_name}: {masked_value}")
        else:
            status = "❌" if is_critical else "⚠️ "
            print(f"  {status} {var_name}: 未設定 - {description}")
            if is_critical:
                all_required_ok = False
    
    print("\n📋 オプション設定:")
    for var_name, description in optional_vars:
        value = os.environ.get(var_name)
        if value:
            # APIキーはマスク、その他はそのまま
            if 'API_KEY' in var_name:
                masked_value = value[:8] + "..." + value[-4:] if len(value) > 12 else "***"
                print(f"  ✅ {var_name}: {masked_value}")
            else:
                print(f"  ✅ {var_name}: {value}")
        else:
            print(f"  ⚪ {var_name}: 未設定 - {description}（オプション）")
    
    return all_required_ok

def main():
    print("🏥 FX News System ヘルスチェック開始")
    print("=" * 50)
    
    # モジュール確認
    modules_ok = check_module_imports()
    
    # 環境変数確認
    env_ok = check_env_variables()
    
    # 結果サマリー
    print("\n" + "=" * 50)
    print("📋 ヘルスチェック結果:")
    
    if modules_ok and env_ok:
        print("✅ 全チェック OK - システム準備完了！")
        print("\n次のステップ:")
        print("  ./scripts/run_alerts.sh      # 速報テスト")
        print("  ./scripts/run_digest_morning.sh  # 朝ダイジェストテスト")
        return 0
    else:
        print("❌ 問題を発見:")
        if not modules_ok:
            print("  - 必要なモジュールが不足")
            print("  - 解決: pip install -r requirements.txt")
        if not env_ok:
            print("  - 必須環境変数が未設定")
            print("  - 解決: .envファイルを設定")
        return 1

if __name__ == "__main__":
    sys.exit(main())