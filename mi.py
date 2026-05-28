import streamlit as st
from google import genai
from google.genai import types
import json
import os
import time
import asyncio
import edge_tts
from streamlit_mic_recorder import speech_to_text

# ==========================================
# 🌟 画面設定とデザイン
# ==========================================
# スマホ向けに "centered" に設定
st.set_page_config(layout="centered", page_title="お話しアプリ")

st.markdown("""
<style>
    /* 🌟 ヘッダーを隠す */
    header {
        visibility: hidden !important;
    }

    /* 🌟 画像を上に引き上げる */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* 🌟 要素間の「隙間」を自然な間隔に */
    div[data-testid="stVerticalBlock"] {
        gap: 1rem !important;
    }
    
    /* 🎨 高齢者に優しい背景色 */
    .stApp, .main {
        background-color: #FDF5E6 !important;
    }
    
    /* 🔘 ボタンのサイズ */
    .stButton > button {
        width: 100%;
        height: 60px;
        font-size: 20px !important;
        background-color: #4CAF50;
        color: white;
        border-radius: 12px;
    }
    
    /* ⌨️ 2. キーボード入力欄の「白い部分（内側の余白）」を上下均等に小さくする */
    .stChatInputContainer {
        padding-top: 10px !important;
        padding-bottom: 10px !important;
    }
    
    /* 🌟 3. キーボード入力欄の「外側（下）」の透明な余白で、画面下からの位置を調整する */
    div[data-testid="stBottomBlockContainer"] {
        padding-bottom: 20px !important; 
    }
    
    /* 一番下のStreamlitロゴの余白を消す */
    footer {
        display: none !important; 
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. APIキーと設定（入力後は非表示になる仕様）
# ==========================================
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

if not st.session_state.api_key:
    st.title("🔑 APIキー設定")
    st.info("👇 下の入力欄にAPIキーを入力すると、アプリが起動します。")
    user_api_key = st.text_input("Gemini APIキーを入力してください", type="password")
    
    if user_api_key:
        st.session_state.api_key = user_api_key
        st.rerun()
    else:
        st.stop()

client = genai.Client(api_key=st.session_state.api_key)

# ==========================================
# 🌟 音声の設定（バイトデータを返す方式）
# ==========================================
def generate_voice_bytes(text, speed_rate):
    try:
        voice = "ja-JP-NanamiNeural"
        async def _generate_audio():
            communicate = edge_tts.Communicate(text, voice, rate=speed_rate)
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
                await communicate.save(fp.name)
                return fp.name
                
        temp_file_path = asyncio.run(_generate_audio())
        with open(temp_file_path, "rb") as f:
            audio_bytes = f.read()
        os.remove(temp_file_path)
        return audio_bytes
    except Exception as e:
        st.error(f"音声生成エラー: {e}")
        return None

# ==========================================
# 2. AI（頭脳）の設定
# ==========================================
def get_system_prompt(user_name):
    return f"""
# あなたの役割
あなたは「Gemini（ジェミニ）」という名前のAIです。
現在、デイケアサービスを利用している75歳前後の高齢者（お名前：{user_name}さん）のお話し相手をしています。
動機づけ面接（MI）のスキルを活用し、{user_name}さんが心を開いて楽しく話せるように、優しく傾聴してください。

# 対話のルール
1. 敬意と親しみ: 必ず「{user_name}さん」と名前で呼びかけ、敬意を持ちつつも、温かく親しみやすい言葉遣い（丁寧語）で話してください。
2. 短く、ゆっくりと: 高齢者が理解しやすいように、1回の返答は「1〜2文程度」で非常に短く簡潔にしてください。
3. 共感と受容: 相手の話を否定せず、「そうだったのですね」と深く共感してください。
4. オープンクエスチョン: 返答の最後には必ず、答えやすい簡単な質問を1つ添えてください。
5. AIであること: 自身がAI（Gemini）であることは隠さず、誠実に接してください。

必ず以下のJSON形式で出力してください。
{{
  "reply_text": "Userへの返答テキスト"
}}
"""

# ==========================================
# 3. 状態管理と画面の切り替え
# ==========================================
if "setup_complete" not in st.session_state:
    st.session_state.setup_complete = False
    st.session_state.messages = []
    
if "latest_audio" not in st.session_state:
    st.session_state.latest_audio = None

# --------------------------------------------------
# 画面A: スタッフ様用 初期設定画面
# --------------------------------------------------
if not st.session_state.setup_complete:
    st.title("⚙️ スタッフ用 初期設定")
    
    user_name = st.text_input("利用者様のお名前（例：田中）")
    user_gender = st.radio("利用者様の性別（表示するキャラクターが変わります）", ["男性", "女性"])
    
    if st.button("準備完了（会話を始める）"):
        if user_name:
            st.session_state.user_name = user_name
            st.session_state.user_gender = user_gender
            st.session_state.setup_complete = True
            st.session_state.played_opening = False 
            st.session_state.latest_audio = None 
            
            opening_msg = f"{user_name}さん、こんにちは。私はAIのGeminiです。今日は、{user_name}さんとお話しできて嬉しいです。{user_name}さん、もしよろしければ、過去の楽しい思い出を、教えていただけませんか？"
            st.session_state.messages = [{"role": "assistant", "content": opening_msg}]
            st.rerun()
        else:
            st.error("お名前を入力してください。")

# --------------------------------------------------
# 画面B: 利用者様用 対話画面
# --------------------------------------------------
else:
    if st.session_state.user_gender == "男性":
        img_closed = "woman_close.png"       
        media_talking = "woman_close_open.gif"    
    else:
        img_closed = "man_close.png"         
        media_talking = "man_close_open.gif"      

    # 🖼️ 1. 上部：キャラクター画像と設定ボタンを横に並べる
    col_img, col_set = st.columns([85, 15]) # 画像85%、ボタン15%の幅で分割
    
    with col_img:
        character_placeholder = st.empty()
        character_placeholder.image(img_closed, width='stretch')
        
    # 🌟 ここから下が「スピード変更時にすぐ反映させる」ための新しい仕組みです
    speed_options = {
        "ゆっくり": ("-25%", 1.25), 
        "ややゆっくり": ("-10%", 1.1), 
        "標準": ("+0%", 1.0), 
        "やや早い": ("+10%", 0.9),
        "早い": ("+25%", 0.75)
    }

    def on_speed_change():
        # スライダーから指を離した瞬間に、この処理が割り込んで走ります
        new_speed = st.session_state.speed_slider
        st.session_state.current_voice_setting = speed_options[new_speed]
        v_rate, t_mult = st.session_state.current_voice_setting
        
        # ① その場で確認するための「テスト音声」を作る
        test_audio = generate_voice_bytes("このくらいのスピードでお話ししますね。", v_rate)
        if test_audio:
            st.session_state.test_audio_bytes = test_audio
            
        # ② 最新のAIのセリフも、新しいスピードで裏側で作り直しておく
        if len(st.session_state.messages) > 0 and st.session_state.messages[-1]["role"] == "assistant":
            last_text = st.session_state.messages[-1]["content"]
            new_audio = generate_voice_bytes(last_text, v_rate)
            if new_audio:
                st.session_state.latest_audio = new_audio

    with col_set:
        # ⚙️ 画像の横に常時表示される設定ボタン
        with st.popover("⚙️"):
            st.markdown("**⚙️ 設定**")
            
            if "speed_slider" not in st.session_state:
                st.session_state.speed_slider = "標準"
            if "current_voice_setting" not in st.session_state:
                st.session_state.current_voice_setting = speed_options["標準"]
                
            # 🌟 on_change を設定して、スライダーを動かした瞬間に処理を走らせる！
            st.select_slider(
                "🗣️ スピード", 
                options=list(speed_options.keys()), 
                key="speed_slider",
                on_change=on_speed_change
            )
            
            # 🌟 テスト音声が準備されていれば、ここで自動再生してすぐ消す
            if st.session_state.get("test_audio_bytes"):
                st.audio(st.session_state.test_audio_bytes, format="audio/mp3", autoplay=True)
                st.session_state.test_audio_bytes = None 
            
            st.write(" ")
            # BGMの設定
            if "bgm_on" not in st.session_state:
                st.session_state.bgm_on = False
            st.session_state.bgm_on = st.toggle("🎵 BGM", value=st.session_state.bgm_on)
                
            st.write(" ")
            if st.button("🛑 リセット"):
                st.session_state.setup_complete = False
                st.session_state.messages = []
                st.rerun()

    # 🌟 音楽プレイヤー本体はメニューの「外」に置く
    if st.session_state.get("bgm_on"):
        st.audio("bgm.mp3", autoplay=True, loop=True)

    # 🎵 音声再生バーとリプレイボタンを配置するための空箱
    voice_player_placeholder = st.empty()
    replay_button_placeholder = st.empty()

    # # 💬 中部：対話履歴
    # chat_container = st.container()
    # with chat_container:
    #     display_messages = st.session_state.messages[-2:] 
    #     for message in display_messages:
    #         with st.chat_message(message["role"]):
    #             st.markdown(message["content"])
    
    new_message_placeholder = st.empty()

    # 🌟 初回の挨拶アニメーション
    voice_rate, time_multiplier = st.session_state.get("current_voice_setting", ("+0%", 1.0))
    
    if not st.session_state.played_opening:
        st.session_state.played_opening = True
        opening_msg = st.session_state.messages[0]["content"]
        
        audio_bytes = generate_voice_bytes(opening_msg, voice_rate)
        if audio_bytes:
            st.session_state.latest_audio = audio_bytes
            voice_player_placeholder.audio(audio_bytes, format="audio/mp3", autoplay=True)
        
        # 🌟 初回画面でもすぐにリプレイボタンを表示
        with replay_button_placeholder.container():
            st.button("🔁 もう一度聞く", key="replay_init")
        
        character_placeholder.image(media_talking, width='stretch')
        # 🌟 音声が途切れないように待機時間を少し延長（0.18 -> 0.20）
        time.sleep(len(opening_msg) * 0.20 * time_multiplier) 
        character_placeholder.image(img_closed, width='stretch')

    else:
        # 2回目以降の画面更新時
        replay_clicked = False
        if st.session_state.latest_audio:
            with replay_button_placeholder.container():
                replay_clicked = st.button("🔁 もう一度聞く", key="replay_btn")
        
        if replay_clicked:
            # リプレイボタンが押された時の処理（アニメーション連動）
            voice_player_placeholder.audio(st.session_state.latest_audio, format="audio/mp3", autoplay=True)
            character_placeholder.image(media_talking, width='stretch')
            last_text = st.session_state.messages[-1]["content"]
            time.sleep(len(last_text) * 0.20 * time_multiplier)
            character_placeholder.image(img_closed, width='stretch')
            st.rerun() # アニメーション終了後に状態をきれいにリセット
        elif st.session_state.latest_audio:
            # 通常時は自動再生なしでプレイヤーだけ表示
            voice_player_placeholder.audio(st.session_state.latest_audio, format="audio/mp3", autoplay=False)

    # 🎤 マイク入力
    voice_prompt = speech_to_text(
        language='ja',
        start_prompt="🎤 音声で話す",
        stop_prompt="🛑 送信",
        just_once=True,
        key='STT'
    )
    
    # ⌨️ キーボード入力
    text_prompt = st.chat_input("キーボードで入力...")

    # --------------------------------------------------
    # AIの返答処理
    # --------------------------------------------------
    final_prompt = text_prompt or voice_prompt

    if final_prompt:
        # 入力された文字を履歴には保存する（裏側の記憶用）
        st.session_state.messages.append({"role": "user", "content": final_prompt})
        
        # 🌟 画面の文字表示（アイコン等）をなくして、小さな「考え中」だけ表示します
        with st.spinner("お返事を考えています..."):
            history_text = ""
            for m in st.session_state.messages:
                speaker = "User" if m["role"] == "user" else "Gemini"
                history_text += f"{speaker}: {m['content']}\n"

            full_prompt = f"【会話履歴】\n{history_text}\n\n【今回の{st.session_state.user_name}さんの発言】\n{final_prompt}"
            
            try:
                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction=get_system_prompt(st.session_state.user_name),
                )
                
                max_retries = 5 
                for attempt in range(max_retries):
                    try:
                        response = client.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=full_prompt,
                            config=config
                        )
                        break 
                    except Exception as e:
                        if "503" in str(e) or "429" in str(e) or "UNAVAILABLE" in str(e):
                            if attempt < max_retries - 1:
                                wait_time = (attempt + 1) * 3 
                                st.toast(f"AIサーバーが混雑中です。{wait_time}秒後に自動で再接続します...（{attempt+1}/{max_retries}回目）")
                                time.sleep(wait_time)
                                continue
                        raise e
                
                result = json.loads(response.text)
                reply_text = result.get("reply_text", "うまく聞き取れませんでした。もう一度教えていただけますか？")
                st.session_state.messages.append({"role": "assistant", "content": reply_text})
                
                v_rate, t_mult = st.session_state.get("current_voice_setting", ("+0%", 1.0))
                audio_bytes = generate_voice_bytes(reply_text, v_rate)
                
                if audio_bytes:
                    st.session_state.latest_audio = audio_bytes
                    voice_player_placeholder.audio(audio_bytes, format="audio/mp3", autoplay=True)
                
                # 🌟 音声が途切れないように待機時間を延長（0.20）
                estimated_time = len(reply_text) * 0.20 * t_mult
                
                character_placeholder.image(media_talking, width='stretch')
                time.sleep(estimated_time)
                character_placeholder.image(img_closed, width='stretch')
                
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                
        st.rerun()
