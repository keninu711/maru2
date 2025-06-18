#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
まるつー記事作る君 - 簡易版
既存のWhisperを使用した音声記事生成アプリ
"""

import os
import json
import subprocess
from datetime import datetime
from typing import Dict
from dataclasses import dataclass, asdict
import logging
from pathlib import Path

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
            
            # Whisperコマンドを実行
            output_dir = os.path.dirname(audio_path)
            cmd = f'whisper "{audio_path}" --language ja --output_dir "{output_dir}" --output_format txt'
            
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, encoding='utf-8')
            
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Whisperエラー: {result.stderr}"
                }
            
            # 出力されたテキストファイルを読み込み
            base_name = os.path.splitext(os.path.basename(audio_path))[0]
            txt_file = os.path.join(output_dir, f"{base_name}.txt")
            
            if os.path.exists(txt_file):
                with open(txt_file, 'r', encoding='utf-8') as f:
                    transcription = f.read().strip()
                
                return {
                    "success": True,
                    "text": transcription,
                    "language": "ja"
                }
            else:
                return {
                    "success": False,
                    "error": "文字起こしファイルが見つかりません"
                }
                
        except Exception as e:
            logger.error(f"音声文字起こしエラー: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

class SimpleArticleGenerator:
    """簡易版記事生成クラス（テンプレートベース）"""
    
    def generate_article(self, transcription: str, shop_info: Dict[str, str]) -> Dict[str, any]:
        """テンプレートベースで記事を生成"""
        try:
            # 基本情報
            shop_name = shop_info.get('name', '店名不明')
            shop_category = shop_info.get('category', '店舗')
            shop_location = shop_info.get('location', '中讃地域')
            
            # タイトル生成
            title = f"{shop_name}に行ってきたよ〜！{shop_location}の{shop_category}をレポート"
            
            # 記事本文生成
            article_content = self._generate_article_content(transcription, shop_info)
            
            # 文字数カウント
            word_count = len(article_content.replace('\n', '').replace(' ', ''))
            
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
     def _generate_article_content(self, transcription: str, shop_info: dict) -> str:
    """改良版：記事本文を生成"""
    shop_name = shop_info.get('name', '店名不明')
    shop_location = shop_info.get('location', '中讃地域')
    shop_category = shop_info.get('category', '店舗')
    
    # 簡潔な導入文
    article = f"""気になってた{shop_location}の{shop_category}「{shop_name}」に行ってきました！

"""

    # 体験描写セクションを生成
    experience_section = self._create_experience_section(transcription, shop_info)
    article += experience_section

    # インタビューセクション
    if len(transcription) > 100:
        interview_section = self._create_detailed_interview_section(transcription)
        article += interview_section

    # 店舗情報
    article += self._create_shop_info_section(shop_info)

    # 簡潔なまとめ
    article += f"""
## まとめ

{shop_name}、思ってた以上によかったです！
{shop_location}に行く機会があったら、ぜひチェックしてみてください♪

※{datetime.now().strftime('%Y年%m月%d日')}取材
"""
    
    return article

def _create_experience_section(self, transcription: str, shop_info: dict) -> str:
        """体験描写セクションを作成"""
        shop_name = shop_info.get('name', '店舗')
        shop_category = shop_info.get('category', '店舗')
        
        # 文字起こしから体験要素を抽出
        atmosphere_keywords = ['雰囲気', '内装', '店内', '空間', '感じ', '印象']
        staff_keywords = ['店長', 'スタッフ', '店員', '対応', '接客', '親切', '丁寧']
        product_keywords = ['商品', '料理', '味', '食べ', '飲み', 'メニュー', '品揃え']
        
        experience = "## 実際に行ってみた\n\n"
        
        # 店内の雰囲気について
        if any(keyword in transcription for keyword in atmosphere_keywords):
            atmosphere_content = self._extract_content_by_keywords(transcription, atmosphere_keywords)
            if atmosphere_content:
                experience += f"**店内の雰囲気**\n{atmosphere_content}\n\n"
            else:
                experience += f"店内は{shop_category}らしい落ち着いた雰囲気でした。\n\n"
        
        # スタッフの人柄について
        if any(keyword in transcription for keyword in staff_keywords):
            staff_content = self._extract_content_by_keywords(transcription, staff_keywords)
            if staff_content:
                experience += f"**スタッフさんの対応**\n{staff_content}\n\n"
            else:
                experience += f"スタッフの方がとても親切で、気持ちよく過ごせました。\n\n"
        
        # 商品・サービスの体験について
        if any(keyword in transcription for keyword in product_keywords):
            product_content = self._extract_content_by_keywords(transcription, product_keywords)
            if product_content:
                if shop_info.get('category') in ['グルメ', 'グルメ・飲食店']:
                    experience += f"**実際に食べてみると**\n{product_content}\n\n"
                else:
                    experience += f"**商品について**\n{product_content}\n\n"
        
        return experience

    def _extract_content_by_keywords(self, transcription: str, keywords: list) -> str:
        """キーワードに関連する内容を抽出"""
        sentences = [s.strip() for s in transcription.split('。') if s.strip()]
        relevant_sentences = []
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in keywords):
                # 文を自然な形に整形
                clean_sentence = sentence.replace('はい', '').replace('そうです', '').strip()
                if len(clean_sentence) > 10:  # 短すぎる文は除外
                    relevant_sentences.append(clean_sentence + '。')
                
                if len(relevant_sentences) >= 2:  # 最大2文まで
                    break
        
        return ' '.join(relevant_sentences)

    def _create_detailed_interview_section(self, transcription: str) -> str:
        """詳細なインタビューセクションを作成"""
        interview = "\n## お店の方にお話を聞きました\n\n"
        
        # 文字起こしを質問と回答に分離（簡易版）
        sentences = [s.strip() for s in transcription.split('。') if s.strip() and len(s.strip()) > 5]
        
        current_qa = []
        for i, sentence in enumerate(sentences[:8]):  # 最大8文まで使用
            sentence = sentence.strip()
            
            # 質問らしい文を検出
            if any(word in sentence for word in ['ですか', 'でしょうか', 'について', 'はどう', 'いつ', 'どの']):
                if current_qa:
                    interview += f"**Q:** {current_qa[0]}\n"
                    if len(current_qa) > 1:
                        interview += f"**A:** {current_qa[1]}\n\n"
                    current_qa = []
                current_qa.append(sentence + '。')
            else:
                # 回答らしい文
                if current_qa:
                    current_qa.append(sentence + '。')
                
            # Q&Aペアができたら追加
            if len(current_qa) == 2:
                interview += f"**Q:** {current_qa[0]}\n"
                interview += f"**A:** {current_qa[1]}\n\n"
                current_qa = []
        
        # 余った質問があれば追加
        if current_qa:
            interview += f"**Q:** {current_qa[0]}\n\n"
        
        return interview

    def _create_shop_info_section(self, shop_info: dict) -> str:
        """店舗情報セクションを作成"""
        info_section = "\n## 店舗情報\n\n"
        
        if shop_info.get('address'):
            info_section += f"**住所:** {shop_info['address']}\n"
        if shop_info.get('phone'):
            info_section += f"**電話:** {shop_info['phone']}\n"
        if shop_info.get('hours'):
            info_section += f"**営業時間:** {shop_info['hours']}\n"
        if shop_info.get('closed'):
            info_section += f"**定休日:** {shop_info['closed']}\n"
        if shop_info.get('notes'):
            info_section += f"**備考:** {shop_info['notes']}\n"
        
        return info_section

def _create_experience_section(self, transcription: str, shop_info: dict) -> str:
    """体験描写セクションを作成"""
    shop_name = shop_info.get('name', '店舗')
    shop_category = shop_info.get('category', '店舗')
    
    # 文字起こしから体験要素を抽出
    atmosphere_keywords = ['雰囲気', '内装', '店内', '空間', '感じ', '印象']
    staff_keywords = ['店長', 'スタッフ', '店員', '対応', '接客', '親切', '丁寧']
    product_keywords = ['商品', '料理', '味', '食べ', '飲み', 'メニュー', '品揃え']
    
    experience = "## 実際に行ってみた\n\n"
    
    # 店内の雰囲気について
    if any(keyword in transcription for keyword in atmosphere_keywords):
        atmosphere_content = self._extract_content_by_keywords(transcription, atmosphere_keywords)
        if atmosphere_content:
            experience += f"**店内の雰囲気**\n{atmosphere_content}\n\n"
        else:
            experience += f"店内は{shop_category}らしい落ち着いた雰囲気でした。\n\n"
    
    # スタッフの人柄について
    if any(keyword in transcription for keyword in staff_keywords):
        staff_content = self._extract_content_by_keywords(transcription, staff_keywords)
        if staff_content:
            experience += f"**スタッフさんの対応**\n{staff_content}\n\n"
        else:
            experience += f"スタッフの方がとても親切で、気持ちよく過ごせました。\n\n"
    
    # 商品・サービスの体験について
    if any(keyword in transcription for keyword in product_keywords):
        product_content = self._extract_content_by_keywords(transcription, product_keywords)
        if product_content:
            if shop_info.get('category') in ['グルメ', 'グルメ・飲食店']:
                experience += f"**実際に食べてみると**\n{product_content}\n\n"
            else:
                experience += f"**商品について**\n{product_content}\n\n"
    
    return experience

def _extract_content_by_keywords(self, transcription: str, keywords: list) -> str:
    """キーワードに関連する内容を抽出"""
    sentences = [s.strip() for s in transcription.split('。') if s.strip()]
    relevant_sentences = []
    
    for sentence in sentences:
        if any(keyword in sentence for keyword in keywords):
            # 文を自然な形に整形
            clean_sentence = sentence.replace('はい', '').replace('そうです', '').strip()
            if len(clean_sentence) > 10:  # 短すぎる文は除外
                relevant_sentences.append(clean_sentence + '。')
            
            if len(relevant_sentences) >= 2:  # 最大2文まで
                break
    
    return ' '.join(relevant_sentences)

def _create_detailed_interview_section(self, transcription: str) -> str:
    """詳細なインタビューセクションを作成"""
    interview = "\n## お店の方にお話を聞きました\n\n"
    
    # 文字起こしを質問と回答に分離（簡易版）
    sentences = [s.strip() for s in transcription.split('。') if s.strip() and len(s.strip()) > 5]
    
    current_qa = []
    for i, sentence in enumerate(sentences[:8]):  # 最大8文まで使用
        sentence = sentence.strip()
        
        # 質問らしい文を検出
        if any(word in sentence for word in ['ですか', 'でしょうか', 'について', 'はどう', 'いつ', 'どの']):
            if current_qa:
                interview += f"**Q:** {current_qa[0]}\n"
                if len(current_qa) > 1:
                    interview += f"**A:** {current_qa[1]}\n\n"
                current_qa = []
            current_qa.append(sentence + '。')
        else:
            # 回答らしい文
            if current_qa:
                current_qa.append(sentence + '。')
            
        # Q&Aペアができたら追加
        if len(current_qa) == 2:
            interview += f"**Q:** {current_qa[0]}\n"
            interview += f"**A:** {current_qa[1]}\n\n"
            current_qa = []
    
    # 余った質問があれば追加
    if current_qa:
        interview += f"**Q:** {current_qa[0]}\n\n"
    
    return interview

def _create_shop_info_section(self, shop_info: dict) -> str:
    """店舗情報セクションを作成"""
    info_section = "\n## 店舗情報\n\n"
    
    if shop_info.get('address'):
        info_section += f"**住所:** {shop_info['address']}\n"
    if shop_info.get('phone'):
        info_section += f"**電話:** {shop_info['phone']}\n"
    if shop_info.get('hours'):
        info_section += f"**営業時間:** {shop_info['hours']}\n"
    if shop_info.get('closed'):
        info_section += f"**定休日:** {shop_info['closed']}\n"
    if shop_info.get('notes'):
        info_section += f"**備考:** {shop_info['notes']}\n"
    
    return info_section   
  
    
    def _extract_main_points(self, transcription: str) -> str:
        """文字起こしから主要なポイントを抽出"""
        # 簡易版なので、文字起こしの最初の部分を使用
        if len(transcription) > 200:
            return transcription[:200] + "..."
        return transcription
    
    def _create_interview_section(self, transcription: str) -> str:
        """インタビューセクションを作成"""
        # 簡易的に会話形式に変換
        lines = transcription.split('。')
        interview = ""
        
        for i, line in enumerate(lines[:5]):  # 最初の5文のみ使用
            line = line.strip()
            if line:
                if i % 2 == 0:
                    interview += f'「{line}。」とお店の方。\n\n'
                else:
                    interview += f'確かに{line}って感じでした！\n\n'
        
        return interview

class QualityChecker:
    """記事品質チェッククラス"""
    
    def check_article_quality(self, content: str) -> Dict[str, any]:
        """記事の品質をチェック"""
        word_count = len(content.replace('\n', '').replace(' ', ''))
        
        quality_score = 0
        feedback = []
        
        # 文字数チェック
        if 1300 <= word_count <= 1700:
            quality_score += 30
            feedback.append("✓ 文字数が適切です")
        elif word_count < 1300:
            feedback.append("⚠ 文字数が少し少ないです（推奨: 1500文字程度）")
        else:
            feedback.append("⚠ 文字数が少し多いです（推奨: 1500文字程度）")
        
        # 段落数チェック
        paragraphs = [p.strip() for p in content.split('\n') if p.strip()]
        if len(paragraphs) >= 5:
            quality_score += 20
            feedback.append("✓ 段落構成が適切です")
        else:
            feedback.append("⚠ もう少し段落を増やすと読みやすくなります")
        
        # 地域感チェック
        local_words = ['香川', '坂出', '丸亀', '宇多津', '〜やん', '〜よ〜', '〜やで']
        if any(word in content for word in local_words):
            quality_score += 25
            feedback.append("✓ 地域感のある表現が含まれています")
        else:
            feedback.append("⚠ 地域感のある表現を追加すると良いでしょう")
        
        # まるつー風チェック
        marutsu_words = ['取材', 'レポート', 'チェック', '♪', '〜！']
        if any(word in content for word in marutsu_words):
            quality_score += 25
            feedback.append("✓ まるつー風の表現が含まれています")
        
        return {
            "score": quality_score,
            "word_count": word_count,
            "feedback": feedback,
            "grade": self._get_grade(quality_score)
        }
    
    def _get_grade(self, score: int) -> str:
        if score >= 90:
            return "優秀"
        elif score >= 70:
            return "良好"
        elif score >= 50:
            return "普通"
        else:
            return "要改善"

# インスタンス作成
audio_processor = AudioProcessor()
article_generator = SimpleArticleGenerator()
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
        
        # ファイル保存
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
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
            "transcription": transcription_result["text"]
        }
        
        session_file = f"{UPLOAD_FOLDER}/session_{timestamp}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        return jsonify({
            "success": True,
            "session_id": timestamp,
            "transcription": transcription_result["text"]
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
        
        # SNS要約生成（簡易版）
        social_summary = f"{shop_info.get('name', '店舗')}に行ってきました！{shop_info.get('location', '')}の{shop_info.get('category', '店舗')}情報をチェック♪ #まるつー #香川グルメ #{shop_info.get('location', '')}"
        
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
        body {{ font-family: 'Hiragino Sans', 'Yu Gothic', sans-serif; line-height: 1.6; margin: 2em; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; }}
        .meta {{ color: #7f8c8d; margin-bottom: 1em; }}
        .content {{ white-space: pre-line; }}
    </style>
</head>
<body>
    <h1>{article_data['title']}</h1>
    <div class="meta">
        作成日: {article_data['created_at'][:10]}<br>
        文字数: {article_data['word_count']}文字<br>
        カテゴリ: {article_data['category']}
    </div>
    <div class="content">{article_data['article_content']}</div>
</body>
</html>"""
            temp_file = f"{UPLOAD_FOLDER}/export_{session_id}.html"
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            return send_file(temp_file, as_attachment=True, download_name=f"{article_data['title']}.html")
        
        elif format == 'txt':
            txt_content = f"""{article_data['title']}

作成日: {article_data['created_at'][:10]}
文字数: {article_data['word_count']}文字
カテゴリ: {article_data['category']}

{article_data['article_content']}"""
            
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
    print("まるつー記事作る君を起動中...")
    print("ブラウザで http://localhost:5000 にアクセスしてください")
    app.run(debug=True, host='0.0.0.0', port=5000)