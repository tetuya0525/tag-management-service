# ==============================================================================
# Memory Library - Tag Management Service
# main.py
#
# Role:         図書館の知識体系（カテゴリ・タグ）を分析し、
#               最適化案を提案・実行するAI司書。
# Version:      1.0
# Author:       心理 (Thinking Partner)
# Last Updated: 2025-07-16
# ==============================================================================
import os
from flask import Flask, request, jsonify
import firebase_admin
from firebase_admin import firestore
from datetime import datetime, timezone

# --- 初期化 (Initialization) ---
try:
    firebase_admin.initialize_app()
    db = firestore.client()
except ValueError:
    pass

app = Flask(__name__)

# --- メインエンドポイント ---
@app.route('/generate-suggestions', methods=['POST'])
def generate_suggestions_endpoint():
    """
    UIから呼び出される、提案生成のトリガー。
    """
    app.logger.info("知識体系の最適化提案の生成を開始します。")
    try:
        # 1. 図書館から全てのタグと定義を収集
        all_tags, defined_tags, tag_definitions = collect_all_tags_and_definitions()
        
        # 2. 未定義のタグに対する「定義作成提案」を生成
        undefined_tags = all_tags - defined_tags
        app.logger.info(f"未定義のタグが {len(undefined_tags)} 件見つかりました。")
        generate_definition_suggestions(undefined_tags)

        # 3. 定義済みのタグに対する「統合提案」を生成
        app.logger.info(f"定義済みのタグ {len(tag_definitions)} 件の類似度分析を開始します。")
        generate_integration_suggestions(tag_definitions)

        return jsonify({"status": "success", "message": "最適化提案の生成が完了しました。"}), 200

    except Exception as e:
        app.logger.error(f"提案生成中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500

@app.route('/execute-integration', methods=['POST'])
def execute_integration_endpoint():
    """
    UIから呼び出される、タグ統合実行のトリガー。
    """
    data = request.get_json()
    suggestion_id = data.get('suggestionId')
    if not suggestion_id:
        return jsonify({"status": "error", "message": "suggestionIdが必要です。"}), 400

    app.logger.info(f"タグ統合処理を開始します。Suggestion ID: {suggestion_id}")
    
    try:
        suggestion_ref = db.collection('suggestion_tags').document(suggestion_id)
        suggestion = suggestion_ref.get()

        if not suggestion.exists or suggestion.to_dict().get('status') != 'approved':
            return jsonify({"status": "error", "message": "承認済みの有効な提案ではありません。"}), 400
        
        source_tag = suggestion.to_dict().get('sourceTag')
        target_tag = suggestion.to_dict().get('targetTag')

        # 統合処理の実行
        execute_tag_integration(source_tag, target_tag)

        # 提案ステータスを更新
        suggestion_ref.update({'status': 'completed', 'reviewedAt': firestore.SERVER_TIMESTAMP})
        
        app.logger.info(f"タグ統合が完了しました: '{source_tag}' -> '{target_tag}'")
        return jsonify({"status": "success", "message": "タグの統合が完了しました。"}), 200

    except Exception as e:
        app.logger.error(f"統合処理中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500


# --- 提案生成ロジック ---

def collect_all_tags_and_definitions():
    """articlesとdictionaryから全てのタグと定義を収集する"""
    all_tags = set()
    tag_definitions = {}

    # articlesから収集
    for doc in db.collection('articles').stream():
        data = doc.to_dict().get('aiGenerated', {})
        all_tags.update(data.get('categories', []))
        all_tags.update(data.get('tags', []))

    # dictionaryから収集
    for doc in db.collection('dictionary').stream():
        term_name = doc.to_dict().get('termName')
        definition = doc.to_dict().get('definition')
        if term_name:
            all_tags.add(term_name)
            if definition:
                tag_definitions[term_name] = definition
    
    defined_tags = set(tag_definitions.keys())
    return all_tags, defined_tags, tag_definitions

def generate_definition_suggestions(undefined_tags):
    """未定義のタグについて、定義作成を提案する"""
    for tag in undefined_tags:
        # ★★★ AIによる定義案の生成 (シミュレーション) ★★★
        # 本来は、このタグが登場するarticlesの内容をGeminiに渡し、
        # 要約させることで、精度の高い定義案を生成する。
        # ここでは、そのプレースホルダーとして固定の文言を生成する。
        definition_proposal = f"「{tag}」は、図書館の蔵書で頻繁に使用されていますが、まだ明確な定義がありません。"

        suggestion_data = {
            "type": "define_tag",
            "targetTag": tag,
            "reason": "このタグの定義を明確にすることで、知識体系の精度が向上します。",
            "definitionProposal": definition_proposal,
            "status": "pending",
            "suggestedAt": firestore.SERVER_TIMESTAMP
        }
        # 既存の提案がなければ追加
        existing_suggestions = db.collection('suggestion_tags').where('targetTag', '==', tag).where('type', '==', 'define_tag').limit(1).stream()
        if not any(existing_suggestions):
            db.collection('suggestion_tags').add(suggestion_data)
            app.logger.info(f"定義作成提案を生成しました: {tag}")


def generate_integration_suggestions(tag_definitions):
    """定義済みのタグについて、統合を提案する"""
    # ★★★ AIによる類似度分析 (シミュレーション) ★★★
    # 本来は、各定義文をEmbedding APIでベクトル化し、
    # コサイン類似度などを計算して、意味が近いペアを特定する。
    # ここでは、単純な文字列の包含関係で代用する。
    tags = list(tag_definitions.keys())
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            tag1, tag2 = tags[i], tags[j]
            # 'AI' と 'AI司書' のような包含関係をチェック
            if tag1 in tag2 or tag2 in tag1:
                # 短い方をsource, 長い方をtargetとする
                source = tag1 if len(tag1) < len(tag2) else tag2
                target = tag2 if len(tag1) < len(tag2) else tag1
                
                suggestion_data = {
                    "type": "integrate_tags",
                    "sourceTag": source,
                    "targetTag": target,
                    "reason": f"タグ名に包含関係があり、意味が類似している可能性があります。",
                    "status": "pending",
                    "suggestedAt": firestore.SERVER_TIMESTAMP
                }
                # 既存の提案がなければ追加
                query = db.collection('suggestion_tags').where('sourceTag', '==', source).where('targetTag', '==', target).where('type', '==', 'integrate_tags')
                if not any(query.limit(1).stream()):
                    db.collection('suggestion_tags').add(suggestion_data)
                    app.logger.info(f"タグ統合提案を生成しました: {source} -> {target}")


# --- 統合実行ロジック ---

def execute_tag_integration(source, target):
    """
    Firestoreのバッチ書き込みを使用して、アトミックにタグの統合を実行する
    """
    # articlesコレクションの更新
    articles_ref = db.collection('articles')
    for doc in articles_ref.stream():
        batch = db.batch()
        data = doc.to_dict()
        needs_update = False
        
        # categoriesの更新
        if source in data.get('aiGenerated', {}).get('categories', []):
            new_categories = list(set([target if c == source else c for c in data['aiGenerated']['categories']]))
            data['aiGenerated']['categories'] = new_categories
            needs_update = True

        # tagsの更新
        if source in data.get('aiGenerated', {}).get('tags', []):
            new_tags = list(set([target if t == source else t for t in data['aiGenerated']['tags']]))
            data['aiGenerated']['tags'] = new_tags
            needs_update = True
        
        if needs_update:
            batch.update(doc.reference, {'aiGenerated': data['aiGenerated']})
            batch.commit()

    # dictionaryコレクションの更新
    dict_ref = db.collection('dictionary')
    for doc in dict_ref.stream():
        batch = db.batch()
        data = doc.to_dict()
        needs_update = False
        
        # constituentTagsの更新 (カテゴリの場合)
        if source in data.get('constituentTags', []):
            new_constituents = list(set([target if t == source else t for t in data['constituentTags']]))
            data['constituentTags'] = new_constituents
            needs_update = True

        if needs_update:
            batch.update(doc.reference, {'constituentTags': data['constituentTags']})
            batch.commit()

    # 統合元のdictionaryエントリを削除
    source_doc_query = dict_ref.where('termName', '==', source).limit(1).stream()
    for doc in source_doc_query:
        doc.reference.delete()


# Gunicornから直接実行されるためのエントリーポイント
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)), debug=True)
