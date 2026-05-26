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
    /* 🌟 余白を削りつつ、上部が見切れないように調整 */
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 1rem !important;
    }
    div[data-testid="stVerticalBlock"] > div {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }
    
    /* 🎨 高齢者に優しい背景色（アイボリー）を設定 */
    .stApp {
        background-color: #FDF5E6 !important;
    }
    
    /* マイクボタンなどを押しやすく大きくする */
    .stButton > button {
        width: 100%;
        height: 80px;
        font-size: 28px !important;
        background-color: #4CAF50;
        color: white;
        border-radius: 15px;
        margin-top: 5px !important;
    }
    
    /* 🌟 対話履歴の文字をLINE（大きめ設定）のような見やすいサイズに変更 */
    div[data-testid="stChatMessageContent"] {
        font-size: 22px !important; /* 16pxから22pxに拡大しました */
        line-height: 1.6 !important; /* 行間を少し広げてさらに読みやすくしました */
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. APIキーと設定（入力後は非表示になる仕様）
# ==========================================
if "api_key" not in st.session_state:
    st.session_state.api_key = ""

if not st.session_state.api_key:
    st.sidebar.title("🔑 APIキー設定")
    user_api_key = st.sidebar.text_input("Gemini APIキーを入力してください", type="password")
    
    if user_api_key:
        st.session_state.api_key = user_api_key
        st.rerun()
    else:
        st.info("👈 サイドバーにAPIキーを入力すると、アプリが起動します。")
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
            
            opening_msg = f"{user_name}さん、こんにちは。私はAIのGeminiです。今日は、{user_name}さんとお話しできて嬉しいです。{user_name}さん、もしよろしければ、過去の楽しい思い出を、教えていただけませんか"
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

    # 🖼️ 上部：キャラクター画像
    character_placeholder = st.empty()
    character_placeholder.image(img_closed, width='stretch')

    # 🎵 音声再生バーとリプレイボタンを配置するための空箱
    voice_player_placeholder = st.empty()
    replay_button_placeholder = st.empty()

    # 💬 中部：対話履歴
    chat_container = st.container()
    with chat_container:
        display_messages = st.session_state.messages[-2:] 
        for message in display_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
    
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
        # 🌟 音声が途切れないように待機時間を少し延長（0.18 -> 0.22 -> 0.14）
        time.sleep(len(opening_msg) * 0.18 * time_multiplier) 
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
            time.sleep(len(last_text) * 0.18 * time_multiplier)
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

    # ⚙️ 設定パネル
    st.markdown("---")
    with st.expander("⚙️ 音声・設定（スタッフ用）", expanded=False):
        speed_options = {"ゆっくり": ("-25%", 1.25), "少しゆっくり": ("-10%", 1.1), "標準": ("+0%", 1.0), "少し早い": ("+10%", 0.9)}
        selected_speed = st.select_slider("🗣️ 話すスピード", options=list(speed_options.keys()), value="標準")
        
        st.session_state.current_voice_setting = speed_options[selected_speed]
        
        st.write(" ")
        bgm_on = st.toggle("🎵 心休まる音楽を流す", value=False)
        if bgm_on:
            st.audio("bgm.mp3", autoplay=True, loop=True)
            
        st.write(" ")
        if st.button("🛑 この会話を終了する（リセット）"):
            st.session_state.setup_complete = False
            st.session_state.messages = []
            st.rerun()

    # --------------------------------------------------
    # AIの返答処理
    # --------------------------------------------------
    final_prompt = text_prompt or voice_prompt

    if final_prompt:
        st.session_state.messages.append({"role": "user", "content": final_prompt})
        
        with new_message_placeholder.container():
            with st.chat_message("user"):
                st.markdown(final_prompt)
                
            with st.chat_message("assistant"):
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
                        
                        st.markdown(reply_text)
                        
                        # 🌟 音声が途切れないように待機時間を少し延長（0.18 -> 0.22 -> 0.14）
                        estimated_time = len(reply_text) * 0.18 * t_mult
                        
                        character_placeholder.image(media_talking, width='stretch')
                        time.sleep(estimated_time)
                        character_placeholder.image(img_closed, width='stretch')
                        
                    except Exception as e:
                        st.error(f"エラーが発生しました: {e}")
                        
        st.rerun()