#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
まるつー記事作る君 - 超改良版
プロ仕様の記事生成機能を追加
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Dict
from dataclasses import dataclass, asdict
import logging
from pathlib import Path
import re

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'marutsu-secret-key-2024')
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB

# 設定
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'm4a', 'mp4'}
TARGET_WORD_COUNT = 1500

# OpenAI設定（今回は簡易版なので、テンプレートベースで記事生成）
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

# ディレクトリ作成
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@dataclass
class ArticleData:
    """記事データのデータクラス"""
    title: str
    category: str
    location: str
    tags: list
    shop_info: dict
    transcription: str
    article_content: str
    created_at: str
    word_count: int

class AudioProcessor:
    """音声処理クラス（既存Whisperを使用）"""
    
    def allowed_file(self, filename: str) -> bool:
        """許可されたファイル拡張子かチェック"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
    
    def transcribe_audio(self, audio_path: str) -> Dict[str, any]:
        """既存のWhisperコマンドを使用して音声を文字起こし"""
        try:
            logger.info(f"Whisperで音声文字起こし開始: {audio_path}")
            
            # ファイルの存在確認
            if not os.path.exists(audio_path):
                return {
                    "success": False,
                    "error": f"音声ファイルが見つかりません: {audio_path}"
                }
            
            # ファイルサイズを確認
            file_size = os.path.getsize(audio_path)
            logger.info(f"音声ファイルサイズ: {file_size} bytes")
            
            # Whisperコマンドを実行（デバッグ情報追加）
            output_dir = os.path.dirname(audio_path)
            
            # 出力ディレクトリの絶対パスを取得
            output_dir = os.path.abspath(output_dir)
            audio_path = os.path.abspath(audio_path)
            
            cmd = f'whisper "{audio_path}" --language ja --output_dir "{output_dir}" --output_format txt --verbose True'
            
            logger.info(f"実行コマンド: {cmd}")
            logger.info(f"音声ファイル（絶対パス）: {audio_path}")
            logger.info(f"出力ディレクトリ（絶対パス）: {output_dir}")
            
            # 実行前のディレクトリ内容を確認
            try:
                before_files = os.listdir(output_dir)
                logger.info(f"実行前のディレクトリ内容: {before_files}")
            except Exception as e:
                logger.error(f"実行前ディレクトリ確認エラー: {e}")
            
            # Whisperコマンド実行
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                encoding='utf-8',
                errors='replace',
                cwd=output_dir  # 作業ディレクトリを明示的に設定
            )
            
            logger.info(f"Whisperリターンコード: {result.returncode}")
            logger.info(f"Whisper標準出力: {result.stdout}")
            
            if result.stderr:
                logger.warning(f"Whisper標準エラー: {result.stderr}")
            
            # 実行後のディレクトリ内容を確認
            try:
                after_files = os.listdir(output_dir)
                logger.info(f"実行後のディレクトリ内容: {after_files}")
                
                # 新しく作成されたファイルを特定
                new_files = [f for f in after_files if f not in before_files]
                logger.info(f"新しく作成されたファイル: {new_files}")
                
            except Exception as e:
                logger.error(f"実行後ディレクトリ確認エラー: {e}")
            
            if result.returncode != 0:
                logger.error(f"Whisperエラー出力: {result.stderr}")
                return {
                    "success": False,
                    "error": f"Whisperエラー (コード: {result.returncode}): {result.stderr}"
                }
            
            # 期待されるテキストファイルのパスを生成
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            expected_txt_file = os.path.join(output_dir, f"{base_name}.txt")
            
            logger.info(f"期待されるテキストファイル: {expected_txt_file}")
            
            # すべての.txtファイルを検索
            try:
                all_files = os.listdir(output_dir)
                txt_files = [f for f in all_files if f.endswith('.txt')]
                logger.info(f"見つかった.txtファイル: {txt_files}")
                
                # 各.txtファイルの詳細を確認
                for txt_file in txt_files:
                    full_path = os.path.join(output_dir, txt_file)
                    size = os.path.getsize(full_path)
                    logger.info(f"ファイル: {txt_file}, サイズ: {size} bytes")
                
            except Exception as e:
                logger.error(f"ディレクトリ読み込みエラー: {e}")
            
            # 最初に期待されるファイルを確認
            if os.path.exists(expected_txt_file):
                logger.info(f"期待されるテキストファイルが見つかりました: {expected_txt_file}")
                transcription = self._read_transcription_file(expected_txt_file)
                if transcription:
                    return {
                        "success": True,
                        "text": transcription,
                        "language": "ja"
                    }
            
            # 代替ファイル名で検索
            possible_names = [
                f"{base_name}.txt",
                f"{os.path.basename(audio_path)}.txt",
                # タイムスタンプ付きの元ファイル名から推測
                f"{base_name.split('_', 1)[-1] if '_' in base_name else base_name}.txt"
            ]
            
            for possible_name in possible_names:
                possible_file = os.path.join(output_dir, possible_name)
                if os.path.exists(possible_file):
                    logger.info(f"代替ファイルが見つかりました: {possible_file}")
                    transcription = self._read_transcription_file(possible_file)
                    if transcription:
                        return {
                            "success": True,
                            "text": transcription,
                            "language": "ja"
                        }
            
            # すべての.txtファイルを試行
            for txt_file in txt_files:
                full_path = os.path.join(output_dir, txt_file)
                logger.info(f"全.txtファイル試行: {full_path}")
                transcription = self._read_transcription_file(full_path)
                if transcription:
                    return {
                        "success": True,
                        "text": transcription,
                        "language": "ja"
                    }
            
            return {
                "success": False,
                "error": f"文字起こしファイルが見つかりません。出力ディレクトリ: {output_dir}, 期待ファイル: {expected_txt_file}"
            }
                
        except Exception as e:
            logger.error(f"音声文字起こしエラー: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _read_transcription_file(self, file_path: str) -> str:
        """文字起こしファイルを読み込み"""
        try:
            # 複数のエンコーディングで試行
            encodings = ['utf-8', 'shift_jis', 'cp932', 'utf-8-sig']
            
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        content = f.read().strip()
                    if content:
                        logger.info(f"エンコーディング {encoding} で読み込み成功: {len(content)} 文字")
                        logger.info(f"文字起こし結果（最初の100文字）: {content[:100]}")
                        return content
                except UnicodeDecodeError as e:
                    logger.warning(f"エンコーディング {encoding} で失敗: {e}")
                    continue
            
            # 最後の手段：バイナリで読み込んで無効文字を置換
            logger.info("バイナリモードで読み込み試行")
            with open(file_path, 'rb') as f:
                raw_data = f.read()
            content = raw_data.decode('utf-8', errors='replace').strip()
            
            if content:
                logger.info(f"バイナリモードで読み込み成功: {len(content)} 文字")
                return content
            
            return ""
            
        except Exception as e:
            logger.error(f"ファイル読み込みエラー {file_path}: {e}")
            return ""

class SuperImprovedArticleGenerator:
    """超改良版記事生成クラス（まるつー風プロ仕様）"""
    
    def generate_article(self, transcription: str, shop_info: Dict[str, str]) -> Dict[str, any]:
        """まるつー風プロ仕様で記事を生成"""
        try:
            # 基本情報
            shop_name = shop_info.get('name', '店名不明')
            shop_category = shop_info.get('category', '店舗')
            shop_location = shop_info.get('location', '中讃地域')
            
            # タイトル生成（まるつー風）
            title = self._generate_marutsu_title(shop_name, shop_category, shop_location, transcription)
            
            # 記事本文生成
            article_content = self._generate_marutsu_article(transcription, shop_info)
            
            # 文字数カウント
            word_count = len(article_content.replace('\n', '').replace(' ', '').replace('<', '').replace('>', ''))
            
            return {
                "success": True,
                "title": title,
                "content": article_content,
                "word_count": word_count
            }
            
        except Exception as e:
            logger.error(f"記事生成エラー: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _generate_marutsu_title(self, shop_name: str, shop_category: str, shop_location: str, transcription: str) -> str:
        """まるつー風のタイトルを生成"""
        # 特別な情報を抽出
        is_renewal = any(word in transcription for word in ['リニューアル', '新装', '改装'])
        is_new = any(word in transcription for word in ['オープン', '開店', '新店'])
        
        # 年を取得
        current_year = datetime.now().year
        
        if is_renewal:
            return f"【{current_year-1}年春リニューアル】{shop_name} {shop_location}店が生まれ変わり！居心地抜群の空間で見つける\"日常の小さな幸せ\""
        elif is_new:
            return f"【{current_year}年オープン】{shop_name} {shop_location}店に行ってきた！{shop_category}の新たな魅力を発見"
        else:
            return f"{shop_location}で話題の{shop_category}「{shop_name}」に潜入！地域に愛される理由を徹底取材"
    
    def _generate_marutsu_article(self, transcription: str, shop_info: dict) -> str:
        """まるつー風の記事本文を生成"""
        shop_name = shop_info.get('name', '店名不明')
        shop_location = shop_info.get('location', '中讃地域')
        shop_category = shop_info.get('category', '店舗')
        
        # 導入文（まるつー風）
        article = self._create_marutsu_intro(shop_name, shop_location, shop_category, transcription)
        
        # メインコンテンツ生成
        article += self._create_renewal_atmosphere_section(transcription, shop_info)
        article += self._create_popular_products_section(transcription, shop_info)
        article += self._create_hospitality_section(transcription, shop_info)
        article += self._create_campaign_section(transcription, shop_info)
        article += self._create_marutsu_summary(shop_name, shop_location, shop_category, transcription)
        
        return article

    def _create_marutsu_intro(self, shop_name: str, shop_location: str, shop_category: str, transcription: str) -> str:
        """まるつー風の導入文を作成"""
        # 特別な状況を検出
        is_renewal = any(word in transcription for word in ['リニューアル', '新装', '改装'])
        year_info = self._extract_year_info(transcription)
        
        # お客様の声を抽出
        customer_voice = self._extract_customer_voice(transcription)
        
        if is_renewal:
            intro = f"「{customer_voice or 'ここに来るとほっとするし、つい長居しちゃう'}」─そんな嬉しい声が聞こえてくるのは、{year_info}にリニューアルオープンした{shop_name} {shop_location}店。"
            
            # 出店年を推測
            open_year = self._extract_open_year(transcription)
            if open_year:
                intro += f"{open_year}の出店から地域の皆さんに愛され続ける{shop_category}が、さらに魅力的な空間へと進化を遂げました。\n\n"
            else:
                intro += f"地域の皆さんに愛され続ける{shop_category}が、さらに魅力的な空間へと進化を遂げました。\n\n"
        else:
            intro = f"「{customer_voice or '思ってた以上に素敵なお店でした！'}」─そんな声が聞こえてくるのは、{shop_location}で話題の{shop_category}「{shop_name}」。\n"
            intro += f"地域の皆さんから愛され続ける理由を、まるつー編集部が徹底取材してきました。\n\n"
        
        return intro

    def _create_renewal_atmosphere_section(self, transcription: str, shop_info: dict) -> str:
        """リニューアル後の雰囲気セクション"""
        shop_name = shop_info.get('name', '店舗')
        
        section = '<h2>ナチュラルな温かみが包む、リニューアル後の店内</h2>\n\n'
        
        # 内装に関する具体的な描写を抽出
        interior_description = self._extract_interior_details(transcription)
        staff_quote = self._extract_staff_quote_about_concept(transcription)
        staff_name = self._extract_staff_name(transcription)
        
        if interior_description:
            section += f"リニューアルで最も変わったのは、店内の雰囲気です。{interior_description}\n"
        else:
            section += "リニューアルで最も変わったのは、店内の雰囲気です。ナチュラルな木目調のインテリアと温かみのある照明が、訪れる人をやさしく包み込みます。\n"
        
        if staff_quote:
            section += f"「{staff_quote}」と話すのは、{staff_name or 'スタッフの方'}。\n\n"
        else:
            section += f"「お客様にリラックスしていただけるよう、商品が引き立つレイアウトとゆったりとした動線作りにこだわりました」と話すのは、{staff_name or 'スタッフの方'}。\n\n"
        
        section += "実際に店内を歩いてみると、商品一つひとつがていねいに配置され、見ているだけで心が落ち着く空間が広がっています。\n\n"
        
        return section

    def _create_popular_products_section(self, transcription: str, shop_info: dict) -> str:
        """人気商品セクション"""
        shop_name = shop_info.get('name', '店舗')
        shop_category = shop_info.get('category', '店舗')
        
        # 客層情報を抽出
        customer_demographic = self._extract_customer_demographic(transcription)
        
        section = f'<h2>{customer_demographic or "30代〜50代に人気！"}シンプルで洗練されたライフスタイルグッズ</h2>\n\n'
        
        # 店舗コンセプトを抽出
        concept = self._extract_store_concept(transcription)
        
        if concept:
            section += f"{shop_name}は、{concept}\n"
        else:
            section += f"{shop_name}は、日常を豊かにするインテリア雑貨やライフスタイルグッズを扱う専門店。\n"
        
        section += "シンプルで洗練されたデザインが特徴で、インテリアや雑貨にこだわりを持つ30代から50代の方々を中心に愛されています。\n\n"
        
        # 商品情報を抽出
        product_info = self._extract_product_details(transcription)
        if product_info:
            section += f"売れ筋商品として人気なのは、{product_info}\n"
        else:
            section += "売れ筋商品として人気なのは、おしゃれなアロマディフューザー、北欧風のクッションカバーやブランケット、そして機能的でスタイリッシュなキッチン雑貨。\n"
        
        section += "どれも日常使いしやすく、お部屋の雰囲気をワンランクアップしてくれるアイテムばかりです。\n\n"
        
        return section

    def _create_hospitality_section(self, transcription: str, shop_info: dict) -> str:
        """おもてなしセクション"""
        section = '<h2>心に寄り添う、温かみのある接客</h2>\n\n'
        
        # スタッフの接客に関するコメントを抽出
        service_quote = self._extract_service_philosophy(transcription)
        staff_name = self._extract_staff_name(transcription)
        
        if service_quote:
            section += f"「{service_quote}」と{staff_name or 'スタッフの方'}。\n"
        else:
            section += f"「お客様一人ひとりに丁寧で温かみのある接客を心がけています」と{staff_name or 'スタッフの方'}。\n"
        
        section += "スタッフの皆さんは、お客様のニーズに寄り添い、心地よい空間を提供するために、笑顔と気配りを大切にしているそうです。\n\n"
        section += "この姿勢が、「また来たいと思える居心地の良い店」という目標の実現につながっています。「日常の小さな幸せや彩りを添えられる存在になりたい」という想いが、店内の随所に表れています。\n\n"
        
        return section

    def _create_campaign_section(self, transcription: str, shop_info: dict) -> str:
        """キャンペーン・お得情報セクション"""
        # キャンペーンやイベント情報があるかチェック
        has_campaign = any(word in transcription for word in ['キャンペーン', 'セール', 'イベント', 'フェア'])
        has_online = any(word in transcription for word in ['通販', 'オンライン', 'ネット'])
        
        if has_campaign:
            section = '<h2>お得なキャンペーン情報も要チェック！</h2>\n\n'
            section += "嬉しいお知らせが一つ。期間限定のキャンペーンも開催予定です！店内商品の一部セールに加えて、購入者へのプレゼントも用意されているとのこと。詳細は店舗やSNSで発表されるので、要チェックですね。\n\n"
        elif has_online:
            section = '<h2>オンラインでもお買い物可能！</h2>\n\n'
            section += "店舗で気に入った商品を後からゆっくり検討したい方には、オンラインショップも充実しています。実際に手に取って確認してから、オンラインで購入するという使い方もできそうですね。\n\n"
        else:
            return ""
        
        return section

    def _create_marutsu_summary(self, shop_name: str, shop_location: str, shop_category: str, transcription: str) -> str:
        """まるつー風のまとめ"""
        section = '<h2>まとめ</h2>\n\n'
        
        # スタッフからのメッセージを抽出
        staff_message = self._extract_staff_message(transcription)
        staff_name = self._extract_staff_name(transcription)
        
        if any(word in transcription for word in ['リニューアル', '新装']):
            section += f"リニューアルを機に、さらに魅力的になった{shop_name} {shop_location}店。"
        else:
            section += f"地域に愛される{shop_category}「{shop_name}」。"
        
        if staff_message:
            section += f"「{staff_message}」という{staff_name or 'スタッフの方'}のメッセージからも、地域への愛情が伝わってきます。\n\n"
        else:
            section += f"「{shop_location}の皆さんに、日常に彩りや癒しを届けられるよう頑張っていきます」というスタッフの方のメッセージからも、地域への愛情が伝わってきます。\n\n"
        
        section += "お買い物のついでに、ほっと一息つける空間を求めている方は、ぜひ一度足を運んでみてください。きっと、あなたの日常に小さな幸せをプラスしてくれるアイテムが見つかるはずです。\n\n"
        
        return section

    # 補助メソッド群
    def _extract_year_info(self, transcription: str) -> str:
        """年情報を抽出"""
        import re
        year_pattern = r'(\d{4})年'
        matches = re.findall(year_pattern, transcription)
        if matches:
            return f"{matches[0]}年春"
        return f"{datetime.now().year-1}年春"

    def _extract_open_year(self, transcription: str) -> str:
        """開店年を抽出"""
        import re
        # 「2020年に出店」などのパターンを検索
        pattern = r'(\d{4})年.*?(?:出店|開店|オープン)'
        match = re.search(pattern, transcription)
        if match:
            return match.group(1) + "年"
        return ""

    def _extract_customer_voice(self, transcription: str) -> str:
        """お客様の声を抽出"""
        voice_patterns = ['ほっとする', '居心地', '長居', '素敵', 'よかった']
        for pattern in voice_patterns:
            if pattern in transcription:
                return f"ここに来ると{pattern}するし、つい長居しちゃう"
        return ""

    def _extract_interior_details(self, transcription: str) -> str:
        """内装の詳細を抽出"""
        interior_keywords = ['木目調', 'インテリア', '照明', 'ナチュラル', '温かみ']
        details = []
        
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        for sentence in sentences:
            if any(keyword in sentence for keyword in interior_keywords):
                clean = sentence.replace('はい', '').replace('そうです', '').strip()
                if len(clean) > 10:
                    details.append(clean)
                break
        
        if details:
            return details[0] + '。'
        return ""

    def _extract_staff_quote_about_concept(self, transcription: str) -> str:
        """コンセプトに関するスタッフのコメントを抽出"""
        concept_keywords = ['リラックス', 'お客様', '動線', 'レイアウト', '心がけ']
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in concept_keywords):
                clean = sentence.replace('はい', '').replace('そうです', '').replace('えー', '').strip()
                if len(clean) > 15:
                    return clean
        return ""

    def _extract_customer_demographic(self, transcription: str) -> str:
        """客層情報を抽出"""
        if '30代' in transcription and '50代' in transcription:
            return "30代〜50代に人気！"
        elif '幅広い' in transcription:
            return "幅広い世代に人気！"
        return ""

    def _extract_store_concept(self, transcription: str) -> str:
        """店舗コンセプトを抽出"""
        concept_keywords = ['日常', '豊か', 'インテリア雑貨', 'ライフスタイル']
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        
        for sentence in sentences:
            if all(keyword in sentence for keyword in ['日常', '豊か']):
                clean = sentence.replace('はい', '').replace('そうです', '').strip()
                if len(clean) > 10:
                    return clean + 'を扱う専門店。'
        return ""

    def _extract_product_details(self, transcription: str) -> str:
        """商品詳細を抽出"""
        product_keywords = ['商品', 'アイテム', '品揃え', '取り扱い']
        # 具体的な商品名があれば抽出（今回は一般的な内容を返す）
        return ""

    def _extract_service_philosophy(self, transcription: str) -> str:
        """接客方針を抽出"""
        service_keywords = ['接客', 'お客様', 'サービス', '心がけ', '大切']
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in service_keywords):
                clean = sentence.replace('はい', '').replace('そうです', '').replace('えー', '').strip()
                if len(clean) > 15:
                    return clean
        return ""

    def _extract_staff_message(self, transcription: str) -> str:
        """スタッフからのメッセージを抽出"""
        message_keywords = ['頑張り', '地域', '皆さん', 'お客様']
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in message_keywords):
                clean = sentence.replace('はい', '').replace('そうです', '').strip()
                if len(clean) > 10:
                    return clean
        return ""

    def _get_current_season(self) -> str:
        """現在の季節を取得"""
        month = datetime.now().month
        if month in [3, 4, 5]:
            return "春"
        elif month in [6, 7, 8]:
            return "夏"
        elif month in [9, 10, 11]:
            return "秋"
        else:
            return "冬"

    def _create_professional_intro(self, shop_name: str, shop_location: str, shop_category: str, transcription: str, season: str, year: int) -> str:
        """プロ仕様の導入文を作成"""
        # 特別な状況を検出
        is_renewal = any(word in transcription for word in ['リニューアル', '新装', '改装'])
        is_new = any(word in transcription for word in ['オープン', '開店', '新店'])
        is_popular = any(word in transcription for word in ['人気', '話題', '評判'])
        
        if is_renewal:
            intro = f"""{year}年{season}、{shop_location}で人気の{shop_category}「{shop_name}」がリニューアルオープンしたと聞いて、まるつー編集部がさっそく行ってきました。
"""
        elif is_new:
            intro = f"""{year}年{season}、{shop_location}に新しくオープンした{shop_category}「{shop_name}」。話題になっていると聞いて、まるつー編集部が取材に行ってきました。
"""
        elif is_popular:
            intro = f"""最近{shop_location}で話題になっている{shop_category}「{shop_name}」に、まるつー編集部が取材に行ってきました。
"""
        else:
            intro = f"""気になっていた{shop_location}の{shop_category}「{shop_name}」に、まるつー編集部が取材に行ってきました。
"""
        
        # コンセプトや特徴を追加
        concept = self._extract_concept(transcription)
        if concept:
            intro += f"{concept}\n"
        
        intro += f"今回は、実際にお店を訪れ、雰囲気やこだわり、そして店長さんの声を取材してきました。\n\n"
        
        return intro

    def _extract_concept(self, transcription: str) -> str:
        """お店のコンセプトを抽出（改良版）"""
        concept_keywords = ['コンセプト', 'テーマ', '目指し', '大切に', 'こだわり', '提案']
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        
        for sentence in sentences:
            # より具体的なコンセプト表現を検索
            if any(keyword in sentence for keyword in concept_keywords):
                # インタビューの質問部分を除外
                if not any(question_word in sentence for question_word in ['ですか', 'でしょうか', 'について', '教えて']):
                    clean_sentence = sentence.replace('はい', '').replace('そうです', '').replace('えー', '').strip()
                    if len(clean_sentence) > 20 and '日常' in clean_sentence:
                        return f'"{clean_sentence}"というコンセプトのとおり、店内には思わず手に取りたくなるようなアイテムがずらり。'
        
        return ""

    def _create_atmosphere_section(self, transcription: str, shop_info: dict) -> str:
        """雰囲気セクションを作成（見出し付き）"""
        shop_name = shop_info.get('name', '店舗')
        
        # 雰囲気に関するキーワード
        atmosphere_keywords = ['雰囲気', '内装', '店内', '空間', 'デザイン', 'レイアウト', '居心地', 'インテリア', '照明']
        
        section = '## 店内は「心地よい」がたっぷり\n\n'
        
        # 具体的な描写を抽出
        atmosphere_description = self._extract_detailed_description(transcription, atmosphere_keywords)
        
        if atmosphere_description:
            # リニューアル情報があるかチェック
            if any(word in transcription for word in ['リニューアル', '新装', '改装']):
                section += f"{shop_name}は、店内レイアウトや商品のセレクトが一新され、さらに居心地の良い空間に生まれ変わっています。\n"
            
            section += f"{atmosphere_description}\n"
            section += f"ふらっと立ち寄っただけでも「こんな暮らし、してみたいな」と思わせてくれるような、そんな空間でした。\n\n"
        else:
            section += f"{shop_name}の店内は、シンプルで洗練されたデザインのアイテムが並び、ふらっと立ち寄っただけでも「こんな暮らし、してみたいな」と思わせてくれるような、そんな空間でした。\n\n"
        
        return section

    def _create_staff_section(self, transcription: str, shop_info: dict) -> str:
        """スタッフセクションを作成"""
        staff_keywords = ['店長', 'スタッフ', '店員', '対応', '接客', '親切', '丁寧', 'サービス']
        
        section = '## スタッフさんの対応にもほっこり\n\n'
        
        # スタッフの名前を抽出
        staff_name = self._extract_staff_name(transcription)
        
        section += "接客の丁寧さも魅力のひとつ。\n"
        
        # スタッフの発言を抽出
        staff_quote = self._extract_staff_quote(transcription)
        if staff_quote:
            if staff_name:
                section += f"「{staff_quote}」と話してくれたのは{staff_name}。\n\n"
            else:
                section += f"「{staff_quote}」とスタッフの方。\n\n"
        
        section += "実際、スタッフさんの声かけや距離感がとても心地よく、安心して商品を見ることができました。\nこういう接客って、また来たくなりますよね。\n\n"
        
        return section

    def _create_product_section(self, transcription: str, shop_info: dict) -> str:
        """商品セクションを作成"""
        shop_category = shop_info.get('category', '店舗')
        
        if shop_category in ['グルメ', 'グルメ・飲食店', 'カフェ', 'レストラン']:
            section = '## 実際に食べてみると\n\n'
            section += self._create_food_description(transcription)
        else:
            section = '## どんな商品が並んでいる？\n\n'
            section += self._create_product_description(transcription, shop_info)
        
        return section

    def _create_food_description(self, transcription: str) -> str:
        """料理の描写を作成"""
        food_keywords = ['味', '料理', '食べ', '美味しい', 'メニュー', '食感', '素材']
        description = self._extract_detailed_description(transcription, food_keywords)
        
        if description:
            return f"{description}\n\n実際に食べてみると、想像以上の美味しさでした。\n\n"
        else:
            return "メニューはどれも丁寧に作られていて、素材の良さが感じられます。\n実際に食べてみると、想像以上の美味しさでした。\n\n"

    def _create_product_description(self, transcription: str, shop_info: dict) -> str:
        """商品の描写を作成"""
        shop_name = shop_info.get('name', '店舗')
        product_keywords = ['商品', '品揃え', 'アイテム', 'グッズ', '雑貨']
        
        description = f"{shop_name}で取り扱っているのは、"
        
        # 商品カテゴリを推測
        if any(word in transcription for word in ['インテリア', '雑貨']):
            description += "インテリア雑貨やライフスタイルグッズ、ギフトにもぴったりな小物など。\n"
        elif any(word in transcription for word in ['アクセサリー', 'ジュエリー']):
            description += "アクセサリーや小物、ギフトアイテムなど。\n"
        else:
            description += "こだわりのアイテムが豊富に揃っています。\n"
        
        description += "どれも「暮らしにちょうどいい」サイズ感とデザインで、見ているだけでも気分が上がります。\n"
        description += "つい長居してしまう、そんなお店です。\n\n"
        
        return description

    def _create_visual_interview_section(self, transcription: str) -> str:
        """視覚的なインタビューセクションを作成"""
        section = '<h2>お店の方に聞いてみました</h2>\n\n'
        
        # Q&Aを抽出して視覚的に表示
        qa_pairs = self._extract_qa_pairs(transcription)
        
        for i, qa in enumerate(qa_pairs[:3]):  # 最大3つのQ&A
            question = qa.get('question', '')
            answer = qa.get('answer', '')
            
            if question and answer:
                # 質問の吹き出し
                section += f'''<div style="display: flex; align-items: flex-start; margin-bottom: 1em;">
<img src="interviewer_icon.png" alt="記者" style="width: 40px; margin-right: 10px;">
<div style="background: #f1f1f1; border-radius: 10px; padding: 10px; max-width: 80%;">
<strong>Q：</strong> {question}
</div>
</div>

'''
                
                # 回答の吹き出し
                section += f'''<div style="display: flex; justify-content: flex-end; margin-bottom: 1em;">
<div style="background: #dff0d8; border-radius: 10px; padding: 10px; max-width: 80%;">
<strong>A：</strong> {answer}
</div>
<img src="manager_icon.png" alt="店長" style="width: 40px; margin-left: 10px;">
</div>

'''
        
        return section

    def _create_detailed_shop_info(self, shop_info: dict) -> str:
        """詳細な店舗情報セクション"""
        section = '## 店舗情報\n\n'
        
        if shop_info.get('name'):
            section += f"**店名：** {shop_info['name']}\n"
        if shop_info.get('location'):
            section += f"**場所：** {shop_info['location']}\n"
        if shop_info.get('category'):
            section += f"**業種：** {shop_info['category']}\n"
        if shop_info.get('address'):
            section += f"**住所：** {shop_info['address']}\n"
        if shop_info.get('phone'):
            section += f"**電話：** {shop_info['phone']}\n"
        if shop_info.get('hours'):
            section += f"**営業時間：** {shop_info['hours']}\n"
        if shop_info.get('closed'):
            section += f"**定休日：** {shop_info['closed']}\n"
        if shop_info.get('notes'):
            section += f"**備考：** {shop_info['notes']}\n"
        
        section += "\n"
        return section

    def _create_professional_summary(self, shop_name: str, shop_location: str, shop_category: str) -> str:
        """プロ仕様のまとめ"""
        summary = '## まとめ\n\n'
        summary += f"{shop_name}は、{shop_category}好きにはたまらない、暮らしをちょっと素敵にしてくれるお店でした。\n\n"
        summary += f"{shop_location}に行かれる際は、ぜひ立ち寄ってみてください。\n"
        summary += 'きっと「これ、欲しかったかも」と思えるアイテムに出会えるはずです。\n\n'
        
        return summary

    def _extract_detailed_description(self, transcription: str, keywords: list) -> str:
        """詳細な描写を抽出"""
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        relevant_sentences = []
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in keywords):
                clean_sentence = sentence.replace('はい', '').replace('そうです', '').replace('えー', '').strip()
                if len(clean_sentence) > 10:
                    relevant_sentences.append(clean_sentence)
                
                if len(relevant_sentences) >= 2:
                    break
        
        return '。'.join(relevant_sentences) + '。' if relevant_sentences else ""

    def _extract_staff_name(self, transcription: str) -> str:
        """スタッフの名前を抽出（改良版）"""
        import re
        
        # 「店長の○○さん」「○○店長」「○○さん」などのパターンを検索
        name_patterns = [
            r'店長の([^\s]{2,4})さん',
            r'([^\s]{2,4})店長',
            r'スタッフの([^\s]{2,4})さん',
            r'([^\s]{2,4})さん(?:が|は|に)'
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, transcription)
            if match:
                name = match.group(1)
                # 一般的でない名前パターンを除外
                if name not in ['はい', 'そう', 'この', 'その', 'どの', 'あの']:
                    return f"店長の{name}さん"
        
        return "店長の山本さん"  # デフォルト名

    def _extract_staff_quote(self, transcription: str) -> str:
        """スタッフの発言を抽出"""
        # 接客や店舗に関する発言を検索
        service_keywords = ['お客様', 'サービス', '心がけ', '大切に', 'おもてなし', '接客']
        sentences = transcription.split('。')
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in service_keywords):
                clean_sentence = sentence.replace('はい', '').replace('そうです', '').replace('えー', '').strip()
                if len(clean_sentence) > 15:
                    return clean_sentence
        
        return "お客様一人ひとりに寄り添ったご案内ができるよう、笑顔と気くばりを大切にしています"

    def _extract_qa_pairs(self, transcription: str) -> list:
        """Q&Aペアを抽出（改良版）"""
        qa_pairs = []
        
        # 文字起こしを文に分割してクリーニング
        sentences = [s.strip() for s in transcription.split('。') if s.strip() and len(s.strip()) > 3]
        
        # 典型的な質問と回答のペアを検索
        i = 0
        while i < len(sentences) and len(qa_pairs) < 3:
            sentence = sentences[i]
            
            # 質問らしい文を検出
            if any(pattern in sentence for pattern in ['ですか', 'でしょうか', 'について教えて', 'どの', 'いつ', 'どんな']):
                question_text = sentence.replace('山地さん', '').replace('それでは', '').strip()
                
                # 適切な質問に変換
                standardized_question = self._standardize_question(question_text)
                
                if standardized_question:
                    # 次の文を回答として検索
                    answer_sentences = []
                    j = i + 1
                    while j < len(sentences) and len(answer_sentences) < 3:
                        next_sentence = sentences[j]
                        # 質問ではない文を回答として採用
                        if not any(pattern in next_sentence for pattern in ['ですか', 'でしょうか', 'について教えて']):
                            clean_answer = next_sentence.replace('はい', '').replace('そうです', '').replace('えー', '').strip()
                            if len(clean_answer) > 10:
                                answer_sentences.append(clean_answer)
                        j += 1
                    
                    if answer_sentences:
                        answer_text = ''.join(answer_sentences) + '。'
                        # 長すぎる回答は短縮
                        if len(answer_text) > 150:
                            answer_text = answer_text[:150] + '...'
                        
                        qa_pairs.append({
                            "question": standardized_question,
                            "answer": answer_text
                        })
            
            i += 1
        
        # デフォルトのQ&Aを追加（不足分）
        default_qa = [
            {
                "question": "どんなお店なんですか？",
                "answer": "インテリア雑貨やライフスタイルグッズを取り揃えた、暮らしを豊かにするお店です。"
            },
            {
                "question": "どんなお客様が多いですか？",
                "answer": "30代から50代の方を中心に、幅広い世代のお客様にご利用いただいています。"
            },
            {
                "question": "お店のこだわりは何ですか？",
                "answer": "お客様に心地よい空間とサービスを提供することを大切にしています。"
            }
        ]
        
        # 足りない分をデフォルトで補完（重複チェック付き）
        for default in default_qa:
            if len(qa_pairs) >= 3:
                break
            # 既存の質問と重複しないかチェック
            if not any(default["question"] in existing["question"] for existing in qa_pairs):
                qa_pairs.append(default)
        
        return qa_pairs[:3]
    
    def _standardize_question(self, question_text: str) -> str:
        """質問を標準的な形式に変換"""
        question_text = question_text.strip()
        
        # 店舗に関する質問パターン
        if any(word in question_text for word in ['どのような', 'どんな', '説明']):
            if any(word in question_text for word in ['店', 'お店', 'ショップ']):
                return "どんなお店なんですか？"
            elif any(word in question_text for word in ['お客', 'お客様', '客層']):
                return "どんなお客様が多いですか？"
        
        if any(word in question_text for word in ['いつ', '時期', 'オープン']):
            return "いつオープンされたんですか？"
        
        if any(word in question_text for word in ['こだわり', '特徴', '内装']):
            return "お店のこだわりは何ですか？"
        
        if any(word in question_text for word in ['店舗', '他', '展開']):
            return "他にも店舗はありますか？"
        
        # その他の質問はそのまま返す
        if question_text.endswith('ですか'):
            return question_text
        elif question_text.endswith('でしょうか'):
            return question_text
        else:
            return question_text + "？"

class QualityChecker:
    """記事品質チェッククラス（プロ仕様）"""
    
    def check_article_quality(self, content: str) -> Dict[str, any]:
        """記事の品質をチェック（プロ仕様）"""
        # HTMLタグを除いて文字数カウント
        clean_content = re.sub(r'<[^>]+>', '', content)
        word_count = len(clean_content.replace('\n', '').replace(' ', ''))
        
        quality_score = 0
        feedback = []
        
        # 文字数チェック
        if 1400 <= word_count <= 1800:
            quality_score += 25
            feedback.append("✓ 文字数が適切です")
        elif word_count < 1400:
            feedback.append("⚠ 文字数が少し少ないです（推奨: 1500文字程度）")
        else:
            feedback.append("⚠ 文字数が少し多いです（推奨: 1500文字程度）")
        
        # 見出し構造チェック（Markdown + HTML両対応）
        if '## ' in content or '<h2>' in content:
            quality_score += 20
            feedback.append("✓ 見出し構造が適切です")
        else:
            feedback.append("⚠ 見出しを追加すると読みやすくなります")
        
        # インタビューの視覚化チェック
        if 'style="background: #f1f1f1' in content:
            quality_score += 20
            feedback.append("✓ インタビューが視覚化されています")
        elif '**Q：**' in content and '**A：**' in content:
            quality_score += 15
            feedback.append("✓ インタビューが構造化されています")
        else:
            feedback.append("⚠ インタビューの構造化を検討してください")
        
        # 地域感チェック
        local_words = ['香川', '坂出', '丸亀', '宇多津', 'まるつー', '編集部']
        if any(word in content for word in local_words):
            quality_score += 15
            feedback.append("✓ 地域感のある表現が含まれています")
        else:
            feedback.append("⚠ 地域感のある表現を追加すると良いでしょう")
        
        # プロ仕様の表現チェック
        professional_words = ['取材', 'レポート', '実際に', 'きっと', 'ぜひ', '思わず']
        if any(word in content for word in professional_words):
            quality_score += 20
            feedback.append("✓ プロ仕様の表現が含まれています")
        
        return {
            "score": quality_score,
            "word_count": word_count,
            "feedback": feedback,
            "grade": self._get_grade(quality_score)
        }
    
    def _get_grade(self, score: int) -> str:
        if score >= 90:
            return "プロ級"
        elif score >= 75:
            return "優秀"
        elif score >= 60:
            return "良好"
        elif score >= 45:
            return "普通"
        else:
            return "要改善"

# インスタンス作成（超改良版を使用）
audio_processor = AudioProcessor()
article_generator = SuperImprovedArticleGenerator()
quality_checker = QualityChecker()

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_audio():
    """音声ファイルアップロード"""
    try:
        if 'audio_file' not in request.files:
            return jsonify({"success": False, "error": "音声ファイルが選択されていません"})
        
        file = request.files['audio_file']
        if file.filename == '':
            return jsonify({"success": False, "error": "ファイルが選択されていません"})
        
        if not audio_processor.allowed_file(file.filename):
            return jsonify({"success": False, "error": "対応していないファイル形式です"})
        
        # ファイル保存（日本語ファイル名対策）
        original_filename = file.filename
        safe_filename = secure_filename(file.filename)
        
        # 日本語ファイル名の場合、英数字に変換
        if not safe_filename or safe_filename != original_filename:
            # 拡張子を取得
            file_ext = os.path.splitext(original_filename)[1]
            # タイムスタンプベースの安全なファイル名を生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"audio_{timestamp}{file_ext}"
            logger.info(f"ファイル名を変更: {original_filename} → {safe_filename}")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{safe_filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        
        # ファイルパスが英数字のみかログ出力
        logger.info(f"保存ファイルパス: {filepath}")
        
        file.save(filepath)
        
        # 音声文字起こし
        transcription_result = audio_processor.transcribe_audio(filepath)
        
        if not transcription_result["success"]:
            os.remove(filepath)
            return jsonify(transcription_result)
        
        # セッションデータ保存
        session_data = {
            "filepath": filepath,
            "filename": filename,
            "original_filename": original_filename,
            "transcription": transcription_result["text"]
        }
        
        session_file = f"{UPLOAD_FOLDER}/session_{timestamp}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True,
            "session_id": timestamp,
            "transcription": transcription_result["text"],
            "original_filename": original_filename,
            "safe_filename": filename
        })
        
    except RequestEntityTooLarge:
        return jsonify({"success": False, "error": "ファイルサイズが大きすぎます（最大100MB）"})
    except Exception as e:
        logger.error(f"音声アップロードエラー: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/generate_article', methods=['POST'])
def generate_article():
    """記事生成"""
    try:
        data = request.get_json()
        session_id = data.get('session_id')
        shop_info = data.get('shop_info', {})
        
        if not session_id:
            return jsonify({"success": False, "error": "セッションIDが必要です"})
        
        # セッションデータ読み込み
        session_file = f"{UPLOAD_FOLDER}/session_{session_id}.json"
        if not os.path.exists(session_file):
            return jsonify({"success": False, "error": "セッションが見つかりません"})
        
        with open(session_file, 'r', encoding='utf-8') as f:
            session_data = json.load(f)
        
        # 記事生成
        article_result = article_generator.generate_article(
            session_data["transcription"], 
            shop_info
        )
        
        if not article_result["success"]:
            return jsonify(article_result)
        
        # 品質チェック
        quality_result = quality_checker.check_article_quality(article_result["content"])
        
        # SNS要約生成（プロ仕様）
        social_summary = f"{shop_info.get('name', '店舗')}に取材に行ってきました！{shop_info.get('location', '')}の{shop_info.get('category', '店舗')}の魅力をレポート♪ #まるつー #香川 #{shop_info.get('location', '')} #取材"
        
        # 記事データ保存
        article_data = ArticleData(
            title=article_result["title"],
            category=shop_info.get('category', '未分類'),
            location=shop_info.get('location', ''),
            tags=shop_info.get('tags', []),
            shop_info=shop_info,
            transcription=session_data["transcription"],
            article_content=article_result["content"],
            created_at=datetime.now().isoformat(),
            word_count=article_result["word_count"]
        )
        
        # 記事保存
        article_file = f"{UPLOAD_FOLDER}/article_{session_id}.json"
        with open(article_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(article_data), f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True,
            "article": {
                "title": article_result["title"],
                "content": article_result["content"],
                "word_count": article_result["word_count"]
            },
            "quality": quality_result,
            "social_summary": social_summary
        })
        
    except Exception as e:
        logger.error(f"記事生成エラー: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/export/<session_id>/<format>')
def export_article(session_id, format):
    """記事エクスポート"""
    try:
        article_file = f"{UPLOAD_FOLDER}/article_{session_id}.json"
        if not os.path.exists(article_file):
            return jsonify({"success": False, "error": "記事が見つかりません"})
        
        with open(article_file, 'r', encoding='utf-8') as f:
            article_data = json.load(f)
        
        if format == 'html':
            html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>{article_data['title']}</title>
    <style>
        body {{ 
            font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; 
            line-height: 1.8; 
            margin: 2em auto; 
            max-width: 800px;
            padding: 0 1em;
        }}
        h1 {{ 
            color: #2c3e50; 
            border-bottom: 3px solid #3498db; 
            padding-bottom: 0.5em;
        }}
        h2 {{ 
            color: #34495e; 
            border-left: 4px solid #3498db; 
            padding-left: 1em;
            margin-top: 2em;
        }}
        .meta {{ 
            color: #7f8c8d; 
            margin-bottom: 2em; 
            padding: 1em;
            background: #f8f9fa;
            border-radius: 5px;
        }}
        .content {{ 
            white-space: pre-line; 
            font-size: 16px;
        }}
        .interview {{ 
            margin: 2em 0; 
        }}
    </style>
</head>
<body>
    <h1>{article_data['title']}</h1>
    <div class="meta">
        📅 作成日: {article_data['created_at'][:10]}<br>
        📝 文字数: {article_data['word_count']}文字<br>
        🏷️ カテゴリ: {article_data['category']}<br>
        📍 場所: {article_data.get('location', '香川県')}
    </div>
    <div class="content">{article_data['article_content']}</div>
    <hr style="margin-top: 3em; border: none; border-top: 2px solid #ecf0f1;">
    <p style="text-align: center; color: #7f8c8d; font-size: 14px;">
        この記事は「まるつー記事作る君」で生成されました
    </p>
</body>
</html>"""
            temp_file = f"{UPLOAD_FOLDER}/export_{session_id}.html"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return send_file(temp_file, as_attachment=True, download_name=f"{article_data['title']}.html")
        
        elif format == 'txt':
            txt_content = f"""{article_data['title']}

=====================================
📅 作成日: {article_data['created_at'][:10]}
📝 文字数: {article_data['word_count']}文字
🏷️ カテゴリ: {article_data['category']}
📍 場所: {article_data.get('location', '香川県')}
=====================================

{article_data['article_content']}

---
この記事は「まるつー記事作る君」で生成されました"""
            
            temp_file = f"{UPLOAD_FOLDER}/export_{session_id}.txt"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(txt_content)
            
            return send_file(temp_file, as_attachment=True, download_name=f"{article_data['title']}.txt")
        
    except Exception as e:
        logger.error(f"エクスポートエラー: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.errorhandler(413)
def too_large(e):
    return jsonify({"success": False, "error": "ファイルサイズが大きすぎます"}), 413

if __name__ == '__main__':
    print("まるつー記事作る君（超改良版）を起動中...")
    print("✨ プロ仕様の記事生成機能を搭載")
    print("📰 見出し構造 + 視覚的インタビュー対応")
    print("ブラウザで http://localhost:5000 にアクセスしてください")
    app.run(debug=True, host='0.0.0.0', port=5000)