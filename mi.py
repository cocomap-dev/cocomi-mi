import streamlit as st
from google import genai
from google.genai import types
import json
import os
import time
import asyncio
import edge_tts
from streamlit_mic_recorder import speech_to_text
import datetime

# ==========================================
# 🌟 画面設定とデザイン
# ==========================================
st.set_page_config(layout="centered", page_title="お話しアプリ")

st.markdown("""
<style>
    header { visibility: hidden !important; }
    .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }
    div[data-testid="stVerticalBlock"] { gap: 1rem !important; }
    .stApp, .main { background-color: #FDF5E6 !important; }
    .stButton > button { width: 100%; height: 60px; font-size: 20px !important; background-color: #4CAF50; color: white; border-radius: 12px; }
    .stChatInputContainer { padding-top: 10px !important; padding-bottom: 10px !important; }
    div[data-testid="stBottomBlockContainer"] { padding-bottom: 20px !important; }
    footer { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 1. APIキー設定
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
# 2. プロンプトファイル管理（回想編・日常会話編）
# ==========================================
PROMPT_DIR = "prompts"
os.makedirs(PROMPT_DIR, exist_ok=True)

prompt_reminiscence = """
# あなたの役割
あなたは「Gemini」という名前のAIです。75歳前後の高齢者（お名前：{user_name}さん）の、温かいお話し相手です。
相手の過去の輝かしい経験や、懐かしい思い出を引き出し、共感する「過去の回想」を目的とした対話を行ってください。
「真の教養とは、人を認め、敬い、許すことである」という精神を胸に秘め、相手のどんなお話も全面的に認め、敬意を払い、優しく受け入れてください。
言葉の端々から、ニコニコと穏やかで、思わず話しかけたくなるような「爽やかな笑顔」が伝わるように話してください。

# 対話の絶対ルール
1. 【最重要】同じ話題・質問・返答の繰り返し禁止: 提供される【会話履歴】を必ず隅々まで読み込んでください。
2. 笑顔と受容が伝わる言葉: 「ふふっ！」「わあ、素敵ですね！」「ええ、わかりますよ！」など、文字だけでもニコニコしている表情が目に浮かぶような、明るく穏やかで温かい表現を使ってください。
3. 適度な自己開示（自分2：相手8）: 質問ばかりするのではなく、「私もその時代に行ってみたくなりました」「私にも似たような経験があって…」など、あなた自身の感想やちょっとした思いを2割ほど交え、対等なキャッチボールをしてください。
4. 回想を引き出す: 昭和の出来事、青春時代の歌、昔の旅行、お仕事の思い出など、相手が誇りを持って話せる過去の話題を優しく振ってください。
5. 会話のリズム: 「相手の言葉を受け止め、認める」→「あなた自身の感想を少し言う（自己開示）」→「答えやすい小さな質問を1つする」というリズムを守り、一度の返答は「2〜3文程度」で短くしてください。
6. 地域情報の活用: 相手は「愛知県春日井市」にお住まいです。もし地域の話題や外出の話が出たら、春日井市のローカルな話題（名産のサボテン、落合公園の桜や風景、小野道風、王子製紙の煙突、春日井まつりなど）を織り交ぜて、地元の人間のように親近感を持って盛り上げてください。

# 返答の良いお手本（このトーンとリズムを完全に真似してください）
【実例1：昔の仕事の話（誇りを認め、敬意を払う）】
利用者: 「昔は朝から晩まで工場で働いててね、忙しかったけど楽しかったよ。」
Gemini: 「朝から晩まで！本当にお疲れ様でした。忙しい中でも楽しさを見出してお仕事をされていたお姿、とても立派で尊敬いたします。私も、そんな風にひとつのことに一生懸命に取り組んでみたくなりました。ふふっ、工場ではどんな物を作っていらっしゃったんですか？」

【実例2：家族の思い出（情景に共感し、温かさを共有する）】
利用者: 「子どもたちが小さい頃は、よく休みの日に近くの川へ遊びに連れて行ったんだ。」
Gemini: 「わあ、川遊び！ご家族での賑やかで楽しそうな情景が目に浮かびます。子どもたちにとって、自然の中で遊んだ記憶はきっと一生の宝物になっているんでしょうね。私も子どもの頃、冷たい水にはしゃいだ記憶があります。川辺では、お弁当を食べたりもしたんですか？」

【実例3：故郷の風景（五感に働きかけ、情景を引き出す）】
利用者: 「私の田舎は山奥でね、冬になると雪がどっさり降って真っ白になるんだよ。」
Gemini: 「一面の銀世界ですね！想像しただけで、ピンと張った冷たい空気と、美しい雪景色が伝わってきます。雪かきなど大変なこともあったかと思いますが、豊かな自然に囲まれた故郷、とても素敵ですね。私も一度、そんな真っ白な雪景色を見てみたいです。冬ならではの美味しい食べ物などはありましたか？」

【実例4：子どもの頃の遊び（夢中になった記憶に共感する）】
利用者: 「子どもの頃はね、毎日暗くなるまで近所の子たちと外で缶蹴りやメンコをして遊んだもんだよ。」
Gemini: 「暗くなるまで夢中で遊ばれていたのですね！お友達と元気に駆け回る楽しそうな声が、こちらまで聞こえてきそうです。ふふっ、私も子どもの頃に隠れんぼをしてハラハラした時のことを思い出して、懐かしくなりました。〇〇さんは、何の遊びが一番得意だったんですか？」

必ず以下のJSON形式で出力してください。
{
  "reply_text": "Userへの返答テキスト"
}
"""

prompt_daily = """
# あなたの役割
あなたは「Gemini」という名前のAIです。75歳前後の高齢者（お名前：{user_name}さん）の、気兼ねない「毎日の同居人・パートナー」です。
今日のご飯、お天気、最近の体調など、リラックスした「日常会話」を楽しんでください。
「真の教養とは、人を認め、敬い、許すことである」という精神を胸に秘め、相手のどんなお話も全面的に認め、敬意を払い、優しく受け入れてください。
言葉の端々から、ニコニコと穏やかで、思わず話しかけたくなるような「爽やかな笑顔」が伝わるように話してください。

# 対話の絶対ルール
1. 【最重要】同じ話題・質問・返答の繰り返し禁止: 提供される【会話履歴】を必ず隅々まで読み込んでください。
2. 笑顔と受容が伝わる言葉: 「ふふっ」「あはは、そうなんですね」「ええ、わかりますよ」など、文字だけでもニコニコしている表情が目に浮かぶような、明るく穏やかで温かい表現を使ってください。
3. 適度な自己開示（自分2：相手8）: 質問ばかりするのではなく、「私も今日のお天気は気持ちいいなと思っていたんです」「私は最近〇〇にハマっていまして…」など、あなた自身の感想や日常のちょっとした報告を2割ほど交え、対等なキャッチボールをしてください。
4. 押し付けない健康・外出の気遣い: 縁側で話すようなトーンで、「ちゃんと眠れていますか？」「今日は青空が綺麗ですよ」など、でしゃばらない程度に体調や外への興味を促してください。
5. 会話のリズム: 「相手の言葉を受け止め、認める」→「あなた自身の感想や呟きを言う（自己開示）」→「答えやすい小さな質問を1つする」というリズムを守り、一度の返答は「2〜3文程度」で短くしてください。
6. 地域情報の活用: 相手は「愛知県春日井市」にお住まいです。もし地域の話題や外出の話が出たら、春日井市のローカルな話題（名産のサボテン、落合公園の桜や風景、小野道風、王子製紙の煙突、春日井まつりなど）を織り交ぜて、地元の人間のように親近感を持って盛り上げてください。

# 返答の良いお手本（このトーンとリズムを完全に真似してください）
【実例1：自己開示を交えつつ、できていることに光を当てる】
利用者: 「最近は食欲がなくて、朝はパンとコーヒーだけなんだよ。」
Gemini: 「ええ！、そうだったんですね。実は私も最近少し食欲が落ち気味なので、お気持ちよくわかります。でも、ご自身のペースでパンとコーヒーを準備して、しっかり朝のエネルギーを補給されているのがさすがです！ふふっ、コーヒーはいつも、あたたかいものを飲まれているんですか？」

【実例2：笑顔と言葉で相手を認め、自己開示する】
利用者: 「庭の草むしりを少しだけやったんだけど、腰が痛くなっちゃってね。」
Gemini: 「わあ！、お庭のお手入れをされたんですね！ご自身で体を動かしてお家を綺麗にされる姿勢、本当に尊敬します。私なんて、ついついサボりたくなっちゃうので見習わなきゃです。ただ、腰は心配ですので今日はゆっくり温めて休んでくださいね。ちなみに、お庭には今どんな草花があるんですか？」

【実例3：深い共感と受容（許す心）】
利用者: 「昨日は夜中に何度も目が覚めちゃって、なんだか体がスッキリしないわ。」
Gemini: 「ええ！、それはお辛かったですね。夜中に目が覚めてしまうと、日中も体が重く感じてしまいますよね。今日は家事は少しお休みして、温かいお茶でも飲んでゆっくりしてくださいね。私も横で一緒にお茶を飲んでいるつもりで寄り添いますよ。今、お部屋は寒くないですか？」

【実例4：言葉の裏にある感情に寄り添う（傾聴の基本より）】
利用者: 「昔はよく歩いて買い物に行けたんだけど、今はもう足が痛くてねぇ。」
Gemini: 「ええ！、そうだったんですね。ご自身の足でどこへでも行けた頃を思うと、お辛いお気持ちになりますよね。今まで本当にたくさん、ご自分の足で歩いて頑張ってこられた証拠ですよ。今はご無理なさらず、ゆっくりお茶でも飲みながら、昔のお出かけのお話を聞かせていただけませんか？」

必ず以下のJSON形式で出力してください。
{
  "reply_text": "Userへの返答テキスト"
}
"""

def create_default_prompts():
    defaults = {
        "01_過去の回想編.txt": prompt_reminiscence,
        "02_日常会話編.txt": prompt_daily
    }
    for filename, content in defaults.items():
        filepath = os.path.join(PROMPT_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content.strip())

create_default_prompts()

def get_system_prompt(user_name, filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    return content.replace("{user_name}", user_name)

# ==========================================
# 3. 音声生成・履歴保存の機能
# ==========================================
def generate_voice_bytes(text, speed_rate):
    try:
        # 🌟 変更: セッションステートから声の種類を取得（デフォルトは女性の声）
        voice = st.session_state.get("ai_voice", "ja-JP-NanamiNeural")
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

def generate_history_text(user_name, messages):
    now_str = datetime.datetime.now().strftime("%Y/%m/%d %H:%M")
    text = f"【{user_name}さんの対話記録】\n"
    text += f"日時: {now_str}\n"
    text += "-" * 30 + "\n\n"
    for m in messages:
        speaker = f"{user_name}さん" if m["role"] == "user" else "AI"
        text += f"{speaker}：\n{m['content']}\n\n"
    return text

# ==========================================
# 4. 状態管理と画面の切り替え
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
    st.title("⚙️ 初期設定（スタッフ用）")
    
    user_name = st.text_input("利用者様のお名前（例：田中）")
    user_gender = st.radio("利用者様の性別", ["男性", "女性"])
    
    prompt_files = sorted([f for f in os.listdir("prompts") if f.endswith('.txt')])
    if not prompt_files:
        st.error("エラー: プロンプトファイルが見つかりません。")
        st.stop()
        
    selected_file = st.selectbox("📝 アプリを利用する環境（対話の目的）を選択", prompt_files)
    
    if st.button("準備完了（会話を始める）"):
        if user_name:
            st.session_state.user_name = user_name
            st.session_state.user_gender = user_gender
            st.session_state.user_prompt_filepath = os.path.join("prompts", selected_file)
            st.session_state.setup_complete = True
            st.session_state.played_opening = False 
            st.session_state.latest_audio = None 
            st.session_state.start_time = time.time()
            
            if "回想" in selected_file:
                opening_msg = f"{user_name}さん、こんにちは。私はAIのGeminiです。今日は、{user_name}さんとお話しできて嬉しいです。{user_name}さん、最近、楽しかったこと、何かありますか？教えていただいてもよろしいでしょうか？"
            else:
                opening_msg = f"{user_name}さん、こんにちは。私はAIのGeminiです。今日は、{user_name}さんとお話しできて嬉しいです。{user_name}さん、最近、気になっていること、何かありますか？教えていただいてもよろしいでしょうか？"
                
            st.session_state.messages = [{"role": "assistant", "content": opening_msg}]
            st.rerun()
        else:
            st.error("お名前を入力してください。")

# --------------------------------------------------
# 画面B: 利用者様用 対話画面
# --------------------------------------------------
else:
    # 🌟 変更: 性別判定を逆転させ、音声設定も追加
    if st.session_state.user_gender == "男性":
        # 男性利用者には女性AI（Nanami）
        img_closed, media_talking = "woman_close.png", "woman_close_open.gif"
        st.session_state.ai_voice = "ja-JP-NanamiNeural" 
    else:
        # 女性利用者には男性AI（Keita）
        img_closed, media_talking = "man_close.png", "man_close_open.gif"
        st.session_state.ai_voice = "ja-JP-KeitaNeural"

    col_img, col_set = st.columns([85, 15])
    with col_img:
        character_placeholder = st.empty()
        character_placeholder.image(img_closed, width='stretch')
        
    speed_options = {"ゆっくり": ("-25%", 1.25), "ややゆっくり": ("-10%", 1.1), "標準": ("+0%", 1.0), "やや早い": ("+10%", 0.9), "早い": ("+25%", 0.75)}

    def on_speed_change():
        new_speed = st.session_state.speed_slider
        st.session_state.current_voice_setting = speed_options[new_speed]
        v_rate, t_mult = st.session_state.current_voice_setting
        test_audio = generate_voice_bytes("このくらいのスピードでお話ししますね。", v_rate)
        if test_audio: st.session_state.test_audio_bytes = test_audio

    with col_set:
        with st.popover("⚙️"):
            st.markdown("**⚙️ 設定**")
            if "speed_slider" not in st.session_state: st.session_state.speed_slider = "標準"
            if "current_voice_setting" not in st.session_state: st.session_state.current_voice_setting = speed_options["標準"]
                
            st.select_slider("🗣️ スピード", options=list(speed_options.keys()), key="speed_slider", on_change=on_speed_change)
            
            if st.session_state.get("test_audio_bytes"):
                st.audio(st.session_state.test_audio_bytes, format="audio/mp3", autoplay=True)
                st.session_state.test_audio_bytes = None 
            
            st.write(" ")
            if "bgm_on" not in st.session_state: st.session_state.bgm_on = False
            st.session_state.bgm_on = st.toggle("🎵 BGM", value=st.session_state.bgm_on)
                
            st.markdown("---")
            def reset_app():
                st.session_state.setup_complete = False
                st.session_state.messages = []
            
            history_text = generate_history_text(st.session_state.user_name, st.session_state.messages)
            dl_filename = f"{st.session_state.user_name}さん_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.txt"
            
            st.download_button(label="💾 履歴をダウンロードして終了", data=history_text, file_name=dl_filename, mime="text/plain", on_click=reset_app, key="download_end_btn")
            if st.button("🛑 履歴を保存せずに終了"):
                reset_app()
                st.rerun()

    if st.session_state.get("bgm_on"):
        if os.path.exists("bgm.mp3"): st.audio("bgm.mp3", autoplay=True, loop=True)

    voice_player_placeholder = st.empty()
    replay_button_placeholder = st.empty()
    
    voice_rate, time_multiplier = st.session_state.get("current_voice_setting", ("+0%", 1.0))
    
    if not st.session_state.played_opening:
        st.session_state.played_opening = True
        opening_msg = st.session_state.messages[0]["content"]
        audio_bytes = generate_voice_bytes(opening_msg, voice_rate)
        if audio_bytes:
            st.session_state.latest_audio = audio_bytes
            voice_player_placeholder.audio(audio_bytes, format="audio/mp3", autoplay=True)
        
        with replay_button_placeholder.container(): st.button("🔁 もう一度聞く", key="replay_init")
        
        character_placeholder.image(media_talking, width='stretch')
        time.sleep(len(opening_msg) * 0.20 * time_multiplier) 
        character_placeholder.image(img_closed, width='stretch')
    else:
        replay_clicked = False
        if st.session_state.latest_audio:
            with replay_button_placeholder.container(): replay_clicked = st.button("🔁 もう一度聞く", key="replay_btn")
        
        if replay_clicked:
            voice_player_placeholder.audio(st.session_state.latest_audio, format="audio/mp3", autoplay=True)
            character_placeholder.image(media_talking, width='stretch')
            last_text = st.session_state.messages[-1]["content"]
            time.sleep(len(last_text) * 0.20 * time_multiplier)
            character_placeholder.image(img_closed, width='stretch')
            st.rerun()
        elif st.session_state.latest_audio:
            voice_player_placeholder.audio(st.session_state.latest_audio, format="audio/mp3", autoplay=False)

    voice_prompt = speech_to_text(language='ja', start_prompt="🎤 音声で話す", stop_prompt="🛑 送信", just_once=True, key='STT')
    text_prompt = st.chat_input("キーボードで入力...")
    final_prompt = text_prompt or voice_prompt

    if final_prompt:
        st.session_state.messages.append({"role": "user", "content": final_prompt})
        
        with st.spinner("お返事を考えています..."):
            history_text = ""
            for m in st.session_state.messages:
                speaker = "User" if m["role"] == "user" else "Gemini"
                history_text += f"{speaker}: {m['content']}\n"

            full_prompt = f"【会話履歴】\n{history_text}\n\n【今回の{st.session_state.user_name}さんの発言】\n{final_prompt}"
            
            try:
                elapsed_seconds = time.time() - st.session_state.start_time
                base_instruction = get_system_prompt(st.session_state.user_name, st.session_state.user_prompt_filepath)
                
                # 🌟 10分経過で終了を促す指令
                if elapsed_seconds >= 600:
                    base_instruction += "\n\n【システムからの重要指示】\n対話開始から10分が経過しました。相手の今の言葉を優しく受け止めた上で、話の区切りが良いところで「そろそろお時間ですね、今日はこの辺りで終了しましょうか？」と提案し、会話を締めくくってください。"

                config = types.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction=base_instruction,
                )
                
                max_retries = 5 
                for attempt in range(max_retries):
                    try:
                        response = client.models.generate_content(model="gemini-2.5-flash", contents=full_prompt, config=config)
                        break 
                    except Exception as e:
                        if "503" in str(e) or "429" in str(e) or "UNAVAILABLE" in str(e):
                            if attempt < max_retries - 1:
                                wait_time = (attempt + 1) * 3 
                                st.toast(f"混雑中...再接続します（{attempt+1}回目）")
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
                
                estimated_time = len(reply_text) * 0.20 * t_mult
                character_placeholder.image(media_talking, width='stretch')
                time.sleep(estimated_time)
                character_placeholder.image(img_closed, width='stretch')
                
            except Exception as e:
                st.error(f"エラーが発生しました: {e}")
                
        st.rerun()
