from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
from dotenv import load_dotenv
import random
from datetime import datetime
import io
import base64
import requests
from PIL import Image, ImageDraw

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///excuse_generator.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


# ── Models ──────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    excuses       = db.relationship('Excuse', backref='user', lazy=True)
    contacts      = db.relationship('EmergencyContact', backref='user', lazy=True)

class Excuse(db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    content             = db.Column(db.Text, nullable=False)
    scenario            = db.Column(db.String(100), nullable=False)
    urgency             = db.Column(db.String(20), nullable=False)
    language            = db.Column(db.String(10), default='en')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    user_id             = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    effectiveness_score = db.Column(db.Float, default=0.0)
    is_favorite         = db.Column(db.Boolean, default=False)

class EmergencyContact(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name         = db.Column(db.String(100), nullable=False)
    phone        = db.Column(db.String(20), nullable=False)
    relationship = db.Column(db.String(50), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── AI Helper ────────────────────────────────────────────────────────────────

def call_claude(system_prompt: str, user_prompt: str, max_tokens: int = 500) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["content"][0]["text"].strip()


# ── Excuse Generator ─────────────────────────────────────────────────────────

class ExcuseGenerator:
    SYSTEM = """You are a creative writer specializing in crafting highly believable, realistic, human-sounding excuses.

Rules:
- PRIORITIZE and WEAVE IN the user's custom context — if they say "my cousin's wedding" or "my laptop charger broke", those MUST appear in the excuse.
- Sound like a real person texting or emailing, not a form letter.
- Include at least one specific concrete detail (time, name, place, object) from the context.
- Match the urgency: low = casual, medium = sincere, high = apologetic and urgent.
- Length: 2–4 natural sentences only.
- Output ONLY the excuse. No quotes, no labels, no preamble."""

    def generate(self, scenario, urgency, language='en', custom_context=''):
        urgency_tone = {'low': 'casual and relaxed', 'medium': 'sincere and genuine', 'high': 'urgent and apologetic'}.get(urgency, 'sincere')
        ctx = f'IMPORTANT - Use this specific context in the excuse: "{custom_context}"' if custom_context.strip() else 'No specific context — create a plausible generic excuse.'
        prompt = f"Scenario: {scenario}\nUrgency tone: {urgency_tone}\nLanguage: {language}\n{ctx}\n\nWrite the excuse:"
        try:
            return call_claude(self.SYSTEM, prompt, 200)
        except Exception:
            return self._fallback(scenario, urgency, custom_context, language)

    def _fallback(self, scenario, urgency, ctx, language='en'):
        fallback_pool = {
            'en': {
                'work': {
                    'high': [
                        "I'm dealing with a sudden family emergency and won't be in today — I'm so sorry for the short notice.",
                        "An urgent issue came up at home and I need to step away immediately — I genuinely apologize for the disruption.",
                        "Something unexpected just happened and I have to handle it right away, so I won't be able to make it in today."
                    ],
                    'medium': [
                        "I woke up feeling quite unwell and my doctor advised I rest today.",
                        "I had a rough night and I'm not at my best this morning, so I need to take the day slower.",
                        "I'm dealing with a health issue that needs my attention right now, so I need to take the day off."
                    ],
                    'low': [
                        "Something came up that I completely forgot about — I'll need to reschedule.",
                        "A scheduling conflict slipped through and I need to move things around.",
                        "I had a mix-up in my calendar and need to rework the timing."
                    ],
                },
                'school': {
                    'high': [
                        "I've been ill since last night and genuinely cannot make it in today.",
                        "A family issue has come up suddenly and I need to leave immediately.",
                        "Something urgent needs my attention right now, so I won't be able to make it in today."
                    ],
                    'medium': [
                        "I have an unexpected family situation I need to handle this morning.",
                        "There's a personal matter that came up unexpectedly and I need to take care of it.",
                        "I wasn't expecting this, but I need to deal with something important before I can come in."
                    ],
                    'low': [
                        "A scheduling conflict I overlooked has come up — my apologies.",
                        "A timing issue came up in my plan and I need to move things around.",
                        "I just realised I have a clash in my schedule and need to reschedule."
                    ],
                },
                'social': {
                    'high': [
                        "Something urgent came up at home — I'm so sorry I can't make it.",
                        "A real emergency has popped up and I need to step away immediately.",
                        "An urgent family matter came up and I won't be able to make it tonight."
                    ],
                    'medium': [
                        "I'm not feeling well and don't want to push through it tonight.",
                        "I started feeling off earlier and need to take it easy for the rest of the evening.",
                        "I'm a bit under the weather and don't think I can make it comfortably."
                    ],
                    'low': [
                        "I double-booked myself and only just realised — really sorry.",
                        "A last-minute clash in my plans came up and I need to move things around.",
                        "I had an unexpected schedule issue and need to reroute my evening."
                    ],
                },
                'family': {
                    'high': [
                        "There's an emergency I need to deal with right away — I'll explain later.",
                        "Something urgent has come up and I need to step away immediately.",
                        "I need to handle a serious issue as soon as possible, so I won't be able to make it."
                    ],
                    'medium': [
                        "Work has been impossible today and I need to ask for a rain check.",
                        "Something personal came up and I need to slow down and handle it.",
                        "I have a situation I need to take care of and won't be able to follow through today."
                    ],
                    'low': [
                        "Something slipped into my calendar — I hope we can reschedule.",
                        "I had a timing mix-up and need to push things back a bit.",
                        "A plan change came up at the last minute, so I need to reschedule."
                    ],
                },
            },
            'hi': {
                'work': {
                    'high': [
                        "मुझे घर में अचानक एक गंभीर स्थिति आ गई है, इसलिए आज मैं काम पर नहीं आ सकता — जल्दी सूचना देने के लिए मुझे खेद है।",
                        "घर पर एक urgent समस्या आ गई है, मुझे तुरंत निकलना पड़ेगा — इस व्यवधान के लिए मैं sincere माफी मांगता हूँ।",
                        "कुछ unexpected हुआ है और मुझे इसे तुरंत संभालना है, इसलिए आज मैं ऑफिस नहीं आ पाऊँगा।"
                    ],
                    'medium': [
                        "आज सुबह मैं काफी अस्वस्थ महसूस कर रहा हूँ और डॉक्टर ने मुझे आराम करने की सलाह दी है।",
                        "कल रात अच्छी नींद नहीं हुई और आज सुबह मैं थोड़ा कमजोर महसूस कर रहा हूँ, इसलिए मुझे दिन को धीरे लेना होगा।",
                        "मेरे लिए एक स्वास्थ्य समस्या सामने आई है, इसलिए मुझे आज थोड़ा आराम करना पड़ेगा।"
                    ],
                    'low': [
                        "कुछ ऐसा हुआ जो मैंने बिल्कुल भूल दिया — मुझे इसे फिर से शेड्यूल करना होगा।",
                        "मेरे कैलेंडर में टाईमिंग की समस्या हो गई है और मुझे चीजें फिर से व्यवस्थित करनी होंगी।",
                        "मुझे अपना शेड्यूल बदलना पड़ा है और मुझे समय पुनः तय करना होगा।"
                    ],
                },
                'school': {
                    'high': [
                        "कल रात से मैं बीमार हूँ और आज मैं स्कूल/कॉलेज नहीं आ सकता।",
                        "घर पर एक पारिवारिक स्थिति अचानक आ गई है और मुझे तुरंत जाना होगा।",
                        "कुछ urgent बात मेरे ध्यान में आ गई है, इसलिए आज मैं नहीं आ सकता।"
                    ],
                    'medium': [
                        "आज सुबह मेरे लिए एक अनपेक्षित पारिवारिक स्थिति आ गई है।",
                        "मेरे सामने एक निजी मसला आया है और मुझे इसे संभालना होगा।",
                        "मैंने उम्मीद नहीं की थी, लेकिन मुझे आज कुछ महत्वपूर्ण काम संभालना है।"
                    ],
                    'low': [
                        "एक शेड्यूलिंग टकराव सामने आ गया है — मुझे क्षमा करें।",
                        "मेरे प्लान में एक समय की समस्या आ गई है और मुझे चीजें बदलनी होंगी।",
                        "मैंने अभी देखा है कि मेरे शेड्यूल में टकराव है और मुझे पुनः शेड्यूल करना होगा।"
                    ],
                },
                'social': {
                    'high': [
                        "घर पर कुछ urgent हो गया है — मुझे बहुत खेद है कि मैं आज नहीं आ सकता।",
                        "एक वास्तविक आपात स्थिति आ गई है और मुझे तुरंत दूर जाना होगा।",
                        "अचानक एक पारिवारिक समस्या सामने आई है और आज मैं नहीं आ पाऊँगा।"
                    ],
                    'medium': [
                        "मैं आज अस्वस्थ महसूस कर रहा हूँ और इस शाम मुझे आराम करना है।",
                        "मैं थोड़ी देर से कमजोर महसूस कर रहा हूँ और आज शाम को मैं ठीक से नहीं आ सकता।",
                        "मैं थोड़ा बीमार हूँ और सोच रहा हूँ कि आज मैं ठीक से नहीं आ सकता।"
                    ],
                    'low': [
                        "मैंने अपना समय दोहरा चुका दिया और अभी समझ आया — माफ करें।",
                        "मेरे प्लान में एक आखिरी समय की टकराव हुआ है और मुझे इसे बदलना होगा।",
                        "मेरे पास एक unexpected शेड्यूल समस्या हुई है और मुझे अपनी शाम को बदलनी होगी।"
                    ],
                },
                'family': {
                    'high': [
                        "मुझे तुरंत एक आपात परिस्थिति संभालनी है — बाद में बताऊँगा।",
                        "कुछ urgent चीज़ सामने आई है और मुझे तुरंत दूर जाना होगा।",
                        "मुझे तुरंत एक गंभीर समस्या को संभालना है, इसलिए मैं नहीं आ पाऊँगा।"
                    ],
                    'medium': [
                        "आज काम बहुत ज्यादा था और मुझे रेन चेक के लिए कहना होगा।",
                        "एक निजी स्थिति सामने आई है और मुझे इसे संभालना है।",
                        "मेरे सामने एक स्थिति है जिसे मुझे अभी संभालना है और आज मैं पूरी तरह नहीं आ पाऊँगा।"
                    ],
                    'low': [
                        "मेरे कैलेंडर में कुछ गलत हो गया — मुझे आशा है कि हम फिर से समय तय कर सकते हैं।",
                        "मेरे शेड्यूल में एक छोटी सी समस्या आई है और मुझे थोड़ा पीछे करना होगा।",
                        "अंतिम समय में प्लान बदल गया है, इसलिए मुझे शेड्यूल बदलना होगा।"
                    ],
                },
            },
            'es': {
                'work': {
                    'high': [
                        "Estoy lidiando con una emergencia familiar repentina y no podré ir hoy — siento mucho la corta notificación.",
                        "Ha surgido un problema urgente en casa y necesito salir de inmediato — sinceramente pido disculpas por la interrupción.",
                        "Algo inesperado acaba de pasar y tengo que resolverlo de inmediato, así que hoy no podré ir."
                    ],
                    'medium': [
                        "Me desperté sintiéndome muy mal y el médico me recomendó descansar hoy.",
                        "Anoche dormí mal y esta mañana no me siento bien, así que necesito tomar el día con calma.",
                        "Estoy lidiando con un problema de salud que requiere mi atención, así que necesito tomarme el día libre."
                    ],
                    'low': [
                        "Algo apareció y se me olvidó por completo — necesito reprogramarlo.",
                        "Hubo un conflicto de horario que se me pasó y necesito reorganizarlo.",
                        "Tuve un pequeño error en mi calendario y necesito ajustar el timing."
                    ],
                },
            },
            'fr': {
                'work': {
                    'high': [
                        "Je fais face à une urgence familiale soudaine et je ne pourrai pas venir aujourd'hui — je suis vraiment désolé pour l'avertissement bref.",
                        "Un problème urgent est survenu à la maison et je dois m'absenter immédiatement — je m'excuse sincèrement pour cette interruption.",
                        "Quelque chose d'inattendu vient de se produire et je dois m'en occuper tout de suite, donc je ne pourrai pas venir aujourd'hui."
                    ],
                    'medium': [
                        "Je me suis réveillé très malade et le médecin m'a conseillé de me reposer aujourd'hui.",
                        "J'ai mal dormi et je me sens faible ce matin, donc je dois prendre la journée plus doucement.",
                        "Je suis confronté à un problème de santé qui demande mon attention, donc je dois prendre la journée."
                    ],
                    'low': [
                        "Quelque chose est arrivé que j'avais complètement oublié — il faut que je reprogramme.",
                        "Un conflit d'horaire m'a échappé et je dois réorganiser tout ça.",
                        "J'ai eu un mélange dans mon calendrier et je dois ajuster les horaires."
                    ],
                },
            },
            'de': {
                'work': {
                    'high': [
                        "Ich habe mit einer plötzlichen Familiennotlage zu tun und kann heute nicht erscheinen — es tut mir leid, dass ich so kurzfristig absagen muss.",
                        "Zu Hause ist ein dringender Fall aufgetreten und ich muss sofort weg — ich entschuldige mich aufrichtig für die Unterbrechung.",
                        "Etwas Unerwartetes ist passiert und ich muss es sofort regeln, deshalb kann ich heute nicht kommen."
                    ],
                    'medium': [
                        "Ich bin heute Morgen ziemlich krank aufgewacht und der Arzt hat mir geraten, mich zu schonen.",
                        "Ich habe schlecht geschlafen und fühle mich heute Morgen nicht gut, deshalb muss ich den Tag ruhiger angehen.",
                        "Ich habe ein Gesundheitsproblem, das meine Aufmerksamkeit braucht, daher muss ich heute frei nehmen."
                    ],
                    'low': [
                        "Es ist etwas dazwischengekommen, das ich komplett vergessen hatte — ich muss es neu planen.",
                        "Ein Terminkonflikt ist mir durchgerutscht und ich muss alles umorganisieren.",
                        "Ich hatte eine Verwechslung im Kalender und muss den Termin neu planen."
                    ],
                },
            },
            'ar': {
                'work': {
                    'high': [
                        "أتعامل مع طارئ عائلي مفاجئ ولن أستطيع الحضور اليوم — أعتذر sincerely عن الإشعار القصير.",
                        "حدثت مشكلة عاجلة في المنزل ويجب أن أبتعد فورًا — أقدم اعتذاري الصادق عن الإزعاج.",
                        "حدث شيء غير متوقع وعلينا التعامل معه فورًا لذلك لن أستطيع الحضور اليوم."
                    ],
                    'medium': [
                        "استيقظت أشعر بعدم الوعي وطلب مني الطبيب الراحة اليوم.",
                        "لم أنم جيدًا وبدأت أشعر بالتعب هذا الصباح، لذلك أحتاج إلى التخفيف اليوم.",
                        "أتعامل مع مشكلة صحية تحتاج انتباهي، لذلك أحتاج إلى أخذ يوم راحة."
                    ],
                    'low': [
                        "حدث شيء نسيتُه تمامًا — سأحتاج إلى إعادة الجدولة.",
                        "حدث تعارض في الجدول وعلينا إعادة الترتيب.",
                        "كانت هناك خلط في التقويم وأحتاج إلى تعديل التوقيت."
                    ],
                },
            },
        }
        scenario_pool = fallback_pool.get(language, fallback_pool['en']).get(scenario, fallback_pool['en']['work'])
        options = scenario_pool.get(urgency, scenario_pool['medium'])
        text = random.choice(options)
        if ctx.strip():
            text += f" It has to do with {ctx[:60]}."
        return text


# ── Email Generator ──────────────────────────────────────────────────────────

class EmailGenerator:
    SYSTEM = """You are a professional email ghostwriter. Write authentic emails that sound like a real person wrote them.

Rules:
- Use the excuse and any context provided as the core of the email.
- Match the tone exactly: professional emails are polished but warm; casual emails are friendly.
- Be concise — nobody writes a novel to call in sick.
- Output format (strictly):
  Subject: <subject line>

  <email body>
- No extra text, labels, or preamble outside this format."""

    def generate(self, recipient_type, tone, excuse, sender_name, recipient_name, context='', language='en'):
        ctx_note = f"Additional context: {context}" if context.strip() else ""
        prompt = (f"Recipient type: {recipient_type}\nTone: {tone}\nSender name: {sender_name}\n"
                  f"Recipient name/title: {recipient_name}\nExcuse: {excuse}\n{ctx_note}\n\nWrite the email:")
        try:
            raw = call_claude(self.SYSTEM, prompt, 400)
            lines = raw.split("\n", 2)
            subject = lines[0].replace("Subject:", "").strip() if lines else "Unable to attend"
            body = "\n".join(lines[1:]).strip() if len(lines) > 1 else raw
            return {"subject": subject, "body": body}
        except Exception:
            return self._fallback(excuse, sender_name, recipient_name, language)

    def _fallback(self, excuse, sender_name, recipient_name, language='en'):
        templates = {
            'en': {
                'subject': f"Unable to attend — {datetime.now().strftime('%B %d')}",
                'body': [
                    f"Dear {recipient_name},\n\nI hope you're well. I wanted to let you know that I need to step away unexpectedly today.\n\nI sincerely apologize for any inconvenience. I'll follow up as soon as possible.\n\nBest regards,\n{sender_name}",
                    f"Hi {recipient_name},\n\nI wanted to inform you that something urgent came up and I won't be able to attend as planned.\n\nI’m sorry for the inconvenience and will keep you posted.\n\nRegards,\n{sender_name}",
                ]
            },
            'hi': {
                'subject': f"आज नहीं आ सकूँगा — {datetime.now().strftime('%d %B')}",
                'body': [
                    f"प्रिय {recipient_name},\n\nमैं आपको बताना चाहता हूँ कि आज मुझे एक अप्रत्याशित स्थिति के कारण उपस्थित नहीं रहना होगा।\n\nइसके लिए मैं क्षमाप्रार्थी हूँ और जल्द ही अपडेट दूँगा।\n\nआभारी,\n{sender_name}",
                    f"नमस्ते {recipient_name},\n\nमैं आपको सूचित करना चाहता हूँ कि कुछ अत्यावश्यक事情 सामने आई है और मैं निर्धारित रूप से उपस्थित नहीं रह पाऊँगा।\n\nइसलिए मैं क्षमा चाहता हूँ और जल्द ही संपर्क करूँगा।\n\nधन्यवाद,\n{sender_name}",
                ]
            },
            'es': {
                'subject': f"No podré asistir — {datetime.now().strftime('%d %B')}",
                'body': [
                    f"Estimado/a {recipient_name},\n\nQuiero informarle que hoy tengo que atender una situación inesperada y no podré asistir como estaba previsto.\n\nSiento mucho cualquier inconveniente y seguiré en contacto lo antes posible.\n\nSaludos cordiales,\n{sender_name}",
                    f"Hola {recipient_name},\n\nQuería avisarte que algo urgente surgió y no podré acudir según lo planeado.\n\nLamento mucho la molestia y te mantendré actualizado.\n\nSaludos,\n{sender_name}",
                ]
            },
            'fr': {
                'subject': f"Impossible de participer — {datetime.now().strftime('%d %B')}",
                'body': [
                    f"Bonjour {recipient_name},\n\nJe voulais vous informer qu'une situation imprévue m'oblige à m'absenter aujourd'hui.\n\nJe m'excuse sincèrement pour ce désagrément et je vous tiendrai au courant dès que possible.\n\nCordialement,\n{sender_name}",
                    f"Salut {recipient_name},\n\nJe voulais vous faire savoir qu'un problème urgent est survenu et que je ne pourrai pas être présent comme prévu.\n\nJe suis désolé pour le dérangement et je vous tiendrai informé rapidement.\n\nBien cordialement,\n{sender_name}",
                ]
            },
            'de': {
                'subject': f"Nicht verfügbar — {datetime.now().strftime('%d. %B')}",
                'body': [
                    f"Hallo {recipient_name},\n\nIch möchte Sie darüber informieren, dass ich heute wegen einer unerwarteten Situation nicht erscheinen kann.\n\nEs tut mir leid für die Unannehmlichkeiten und ich werde Sie so schnell wie möglich auf dem Laufenden halten.\n\nMit freundlichen Grüßen,\n{sender_name}",
                    f"Liebe/r {recipient_name},\n\nIch wollte Ihnen mitteilen, dass ein dringender Fall aufgetreten ist und ich nicht wie geplant teilnehmen kann.\n\nIch entschuldige mich für die Unannehmlichkeiten und halte Sie zeitnah auf dem Laufenden.\n\nViele Grüße,\n{sender_name}",
                ]
            },
            'ar': {
                'subject': f"لن أستطيع الحضور — {datetime.now().strftime('%d %B')}",
                'body': [
                    f"عزيزي {recipient_name},\n\nأود إبلاغك بأنني سأحتاج إلى التراجع اليوم بسبب موقف غير متوقع.\n\nأعتذر عن أي إزعاج وسأتواصل معك في أقرب وقت ممكن.\n\nمع الاحترام،\n{sender_name}",
                    f"مرحباً {recipient_name},\n\nأرغب في إبلاغك بحدوث مشكلة عاجلة ولن أستطيع الحضور كما كان مخططًا له.\n\nأنا آسف جدًا للإزعاج وسأعطيك تحديثًا قريبًا.\n\nالأحترام،\n{sender_name}",
                ]
            },
        }
        selected = templates.get(language, templates['en'])
        return {
            "subject": random.choice([selected['subject']]),
            "body": random.choice(selected['body'])
        }


# ── Apology Generator ────────────────────────────────────────────────────────

class ApologyGenerator:
    SYSTEM = """You are an expert at writing sincere, believable apologies that feel genuinely human.

Rules:
- Reference the specific situation from context provided.
- Match the style: professional = composed; emotional = heartfelt; casual = friendly; formal = structured.
- Acknowledge impact on the other person.
- Offer something constructive.
- 3–5 sentences. Output ONLY the apology text."""

    STYLES = {
        'professional': 'formal, composed, taking responsibility without over-explaining',
        'emotional':    'heartfelt, vulnerable, showing genuine remorse',
        'casual':       'friendly, genuine, not overly formal',
        'formal':       'structured, respectful, with offer to remediate',
    }

    def generate(self, style, context, language='en'):
        style_desc = self.STYLES.get(style, 'sincere and appropriate')
        prompt = f"Style: {style} ({style_desc})\nLanguage: {language}\nSituation: {context}\n\nWrite the apology:"
        try:
            return call_claude(self.SYSTEM, prompt, 200)
        except Exception:
            multilingual = {
                'en': {
                    'professional': [
                        "I sincerely apologize — I take full responsibility and will ensure this doesn't happen again.",
                        "I’m truly sorry for the disruption and I’ll make sure I handle this properly moving forward."
                    ],
                    'emotional': [
                        "I'm truly sorry. I feel awful about this and genuinely want to make it right.",
                        "I’m deeply sorry for the hurt and stress this caused, and I want to fix it properly."
                    ],
                    'casual': [
                        "Hey, I'm really sorry about that — it wasn't okay and I'll fix it.",
                        "I’m sorry for the confusion here, and I’ll make sure it’s sorted out."
                    ],
                    'formal': [
                        "Please accept my sincere apologies. I will take immediate steps to address the matter.",
                        "I sincerely regret this and will take prompt corrective action to resolve it."
                    ]
                },
                'hi': {
                    'professional': [
                        "मैं पूरी जिम्मेदारी लेता हूँ और सुनिश्चित करूँगा कि यह दोबारा नहीं होगा।",
                        "मैं इस व्यवधान के लिए क्षमाप्रार्थी हूँ और आगे से इसे सही तरीके से संभालूँगा।"
                    ],
                    'emotional': [
                        "मैं इस स्थिति के लिए बहुत दुखी हूँ और इसे ठीक करने के लिए पूरी मेहनत करूँगा।",
                        "मैं इस स्थिति से बहुत व्यथित हूँ और इसे सही करने के लिए उचित कदम उठाऊँगा।"
                    ],
                    'casual': [
                        "अरे, इसके लिए मैं खेद महसूस कर रहा हूँ — यह सही नहीं था और मैं इसे ठीक करूँगा।",
                        "मैं इसके लिए खेद व्यक्त करता हूँ और इसे सही करने की कोशिश करूँगा।"
                    ],
                    'formal': [
                        "कृपया मेरी क्षमा स्वीकार करें। मैं तुरंत इस मामले को सुधारने के लिए कदम उठाऊँगा।",
                        "मैं इस स्थिति के लिए अत्यंत दुखी हूँ और उचित सुधारात्मक कदम उठाऊँगा।"
                    ]
                },
                'es': {
                    'professional': [
                        "Sinceramente pido disculpas — asumo toda la responsabilidad y aseguraré que esto no vuelva a suceder.",
                        "Lamento profundamente esta situación y tomaré medidas para corregirla de forma adecuada."
                    ],
                    'emotional': [
                        "Lo siento de verdad. Me siento horrible por esto y de verdad quiero arreglarlo.",
                        "Me arrepiento profundamente por el daño causado y quiero hacer las cosas bien."
                    ],
                    'casual': [
                        "Oye, lo siento mucho por eso — no estuvo bien y lo voy a arreglar.",
                        "Te pido disculpas por esto y voy a resolverlo de forma correcta."
                    ],
                    'formal': [
                        "Acepte mis sinceras disculpas. Tomaré medidas inmediatas para resolver este asunto.",
                        "Lamento profundamente esta situación y tomaré las acciones necesarias para corregirla."
                    ]
                },
                'fr': {
                    'professional': [
                        "Je m'excuse sincèrement — j'assume toute la responsabilité et je veillerai à ce que cela ne se reproduise plus.",
                        "Je suis vraiment désolé pour cette interruption et je prendrai les mesures nécessaires pour corriger cela."
                    ],
                    'emotional': [
                        "Je suis vraiment désolé. Je me sens terrible à propos de cela et je veux vraiment arranger les choses.",
                        "Je regrette profondément cette situation et je veux réellement faire amende honorable."
                    ],
                    'casual': [
                        "Hé, je suis vraiment désolé pour ça — ce n'était pas bien et je vais corriger ça.",
                        "Je suis désolé pour la confusion et je vais régler ça proprement."
                    ],
                    'formal': [
                        "Veuillez accepter mes sincères excuses. Je prendrai immédiatement des mesures pour remédier à ce problème.",
                        "Je regrette profondément cet incident et agirai rapidement pour le corriger."
                    ]
                },
                'de': {
                    'professional': [
                        "Ich entschuldige mich aufrichtig — ich übernehme die volle Verantwortung und werde sicherstellen, dass es nicht erneut passiert.",
                        "Es tut mir leid für diese Unterbrechung und ich werde in Zukunft richtig handeln."
                    ],
                    'emotional': [
                        "Es tut mir wirklich leid. Ich fühle mich schrecklich deswegen und möchte es wirklich wieder gutmachen.",
                        "Ich bedaure diese Situation zutiefst und möchte die Dinge ordnungsgemäß korrigieren."
                    ],
                    'casual': [
                        "Hey, es tut mir wirklich leid — das war nicht okay und ich werde es korrigieren.",
                        "Es tut mir leid für die Verwirrung und ich mache das wieder gut."
                    ],
                    'formal': [
                        "Bitte nehmen Sie meine aufrichtigen Entschuldigungen an. Ich werde sofort Schritte unternehmen, um die Angelegenheit zu beheben.",
                        "Ich bedauere diesen Vorfall zutiefst und werde sofort geeignete Maßnahmen ergreifen."
                    ]
                },
                'ar': {
                    'professional': [
                        "أنا أعتذر sincerely — أنا أتحمل المسؤولية بالكامل وسأضمن ألا يحدث هذا مرة أخرى.",
                        "أنا آسف جدًا بشأن هذا الإزعاج وسأتعامل مع الأمر بشكل صحيح في المستقبل."
                    ],
                    'emotional': [
                        "أنا آسف جدًا. أشعر بالأسف الشديد حيال هذا وأرغب حقًا في تصحيح الأمر.",
                        "أشعر بالحزن الشديد تجاه هذه الحالة وأرغب في إصلاحها بشكل صحيح."
                    ],
                    'casual': [
                        "يا صاحب، أنا آسف جدًا بشأن هذا — لم يكن الأمر جيدًا وسأصلحه.",
                        "أنا آسف للإزعاج وسأحاول حل هذه المشكلة بشكل صحيح."
                    ],
                    'formal': [
                        "يرجى قبول اعتذاري الصادق. سأتخذ خطوات فورية لمعالجة هذه المسألة.",
                        "أعتذر بشدة عن هذا الحادث وسأتخذ الإجراءات اللازمة لتصحيحه."
                    ]
                },
            }
            lang_variants = multilingual.get(language, multilingual['en'])
            options = lang_variants.get(style, lang_variants['professional'])
            return random.choice(options)


# ── Emergency System ─────────────────────────────────────────────────────────

class EmergencySystem:
    SCENARIOS = {
        'family_emergency': {
            'label': 'Family Emergency',
            'icon': '🏠',
            'script': ["I just got an urgent call — there's been an emergency at home and I need to leave right now. I'm so sorry.",
                       "Family emergency — I have to go immediately. I'll explain everything when I can. So sorry.",
                       "Something has happened at home and I need to leave right away. I genuinely apologize for the disruption."],
            'sms': ["Family emergency. Leaving now. So sorry — will call when I can 🙏",
                    "Emergency at home. Have to go. Will explain later. Sorry.",
                    "Something urgent at home. Can't stay. Really sorry 🙏"]
        },
        'medical': {
            'label': 'Medical Emergency',
            'icon': '🏥',
            'script': ["I'm not feeling well at all — something is seriously wrong and I need to get to a doctor immediately.",
                       "I've been hit with sudden severe symptoms. I need to leave and get medical attention right away.",
                       "I'm having a medical issue and need to go to urgent care immediately. I'm so sorry."],
            'sms': ["Feeling very unwell, heading to urgent care. So sorry 😔",
                    "Medical issue came up. Had to leave. Will update you. Really sorry.",
                    "Not well at all — going to get checked. Sorry for the sudden exit 🙏"]
        },
        'work_crisis': {
            'label': 'Work Crisis',
            'icon': '💼',
            'script': ["I just got an urgent call from my office — there's a crisis I absolutely have to handle right now. I apologize.",
                       "Work emergency just came in. My boss needs me immediately. I'm terribly sorry to leave like this.",
                       "There's a critical situation at work and I'm the only one who can handle it. I need to step away urgently."],
            'sms': ["Work crisis just came up. Have to deal with it now. So sorry!",
                    "Urgent call from work. Stepping away immediately. Will reschedule ASAP.",
                    "Major work emergency. Can't ignore it. Really sorry 😓"]
        },
        'car_breakdown': {
            'label': 'Car Breakdown',
            'icon': '🚗',
            'script': ["My car has broken down on the way — I'm stuck on the side of the road waiting for roadside assistance.",
                       "I'm stranded — the engine warning light came on and the car has stopped completely. I've called for help.",
                       "Car trouble — it won't start and I'm waiting for a tow truck. I'm incredibly sorry about this."],
            'sms': ["Car broke down 😓 Waiting for roadside help. So sorry, won't make it.",
                    "Stuck with car trouble. Called for help. Really sorry about this.",
                    "Car issues — completely stranded. So embarrassed. Will sort it out 🙏"]
        },
    }

    def trigger(self, scenario_key, contact_name, contact_phone, mode):
        s = self.SCENARIOS.get(scenario_key, self.SCENARIOS['family_emergency'])
        msg = random.choice(s['sms'] if mode == 'sms' else s['script'])
        return {'type': mode, 'scenario': s['label'], 'icon': s['icon'],
                'contact': contact_name, 'phone': contact_phone,
                'message': msg, 'timestamp': datetime.now().strftime('%I:%M %p')}

    def get_scenarios(self):
        return [{'key': k, 'label': v['label'], 'icon': v['icon']} for k, v in self.SCENARIOS.items()]


# ── Proof Generator ──────────────────────────────────────────────────────────

class ProofGenerator:
    def generate(self, proof_type, scenario, custom_name='', custom_org='', excuse_text=''):
        name = custom_name or 'Rahul Sharma'
        org  = custom_org  or ('City General Hospital' if proof_type == 'medical' else 'Acme Corp')
        date = datetime.now().strftime('%B %d, %Y')
        ref  = f'REF-{random.randint(10000,99999)}'
        img = Image.new('RGB', (900, 660), '#ffffff')
        d   = ImageDraw.Draw(img)
        methods = {'medical': self._medical, 'transportation': self._transport,
                   'technical': self._technical}
        methods.get(proof_type, self._generic)(d, img, name, org, date, ref, scenario)
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()

    def _txt(self, d, xy, text, fill, size=14):
        d.text(xy, text, fill=fill)

    def _medical(self, d, img, name, org, date, ref, scenario):
        d.rectangle([0,0,900,660], fill='#f8fafc')
        d.rectangle([0,0,900,115], fill='#1e40af')
        d.rectangle([0,115,900,122], fill='#3b82f6')
        d.text((35,22), 'MEDICAL CERTIFICATE', fill='white')
        d.text((35,68), org, fill='#bfdbfe')
        d.rectangle([820,18,872,30], fill='white'); d.rectangle([840,4,852,48], fill='white')
        d.line([35,148,865,148], fill='#e2e8f0', width=1)
        d.text((35,160), 'CERTIFICATE OF MEDICAL ATTENDANCE', fill='#1e40af')
        d.line([35,192,865,192], fill='#dbeafe', width=2)
        rows = [('Patient Name:', name), ('Date of Visit:', date),
                ('Attending Physician:', f"Dr. {random.choice(['S. Patel','A. Sharma','R. Mehta','P. Singh'])}"),
                ('Diagnosis:', random.choice(['Acute febrile illness','Viral infection','Gastroenteritis','Migraine with aura'])),
                ('Recommended Rest:', '1–2 days from date of visit')]
        for i,(label,val) in enumerate(rows):
            y = 215 + i*38
            d.text((35,y), label, fill='#64748b')
            d.text((230,y), val, fill='#0f172a')
        d.rectangle([35,430,865,490], fill='#eff6ff')
        d.rectangle([35,430,41,490], fill='#3b82f6')
        d.text((56,443), 'This certifies the above-named patient was examined and is advised rest', fill='#1e3a8a')
        d.text((56,468), 'for the period stated. Issued for official/employer submission.', fill='#1e3a8a')
        for i in range(12):
            x1=140+i*13; y1=530+random.randint(-7,7); x2=153+i*13; y2=530+random.randint(-7,7)
            d.line([x1,y1,x2,y2], fill='#1e40af', width=2)
        d.text((35,555), f"MCI Reg No: MCI-{random.randint(100000,999999)}", fill='#64748b')
        d.text((35,578), f"Hospital Lic: {org[:4].upper()}-{random.randint(1000,9999)}", fill='#64748b')
        d.rectangle([660,500,865,590], outline='#3b82f6', width=2)
        d.text((672,514), 'OFFICIAL SEAL', fill='#3b82f6'); d.text((672,542), org[:18], fill='#1e40af')
        d.rectangle([0,610,900,660], fill='#f1f5f9')
        d.text((35,630), f'Ref: {ref}  |  Issued: {date}  |  Valid 48 hours from issue', fill='#94a3b8')

    def _transport(self, d, img, name, org, date, ref, scenario):
        d.rectangle([0,0,900,660], fill='#fffbeb')
        d.rectangle([0,0,900,115], fill='#92400e')
        d.rectangle([0,115,900,122], fill='#f59e0b')
        d.text((35,22), 'TRANSPORTATION DISRUPTION NOTICE', fill='white')
        d.text((35,68), 'Public Transit Authority — Passenger Certificate', fill='#fde68a')
        d.text((35,142), 'SERVICE DISRUPTION CERTIFICATE', fill='#92400e')
        d.line([35,172,865,172], fill='#fde68a', width=2)
        inc_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{random.randint(100,999)}"
        line = random.choice(['Metro Line 3 – Blue','Bus Route 47A','Express Rail – Central','Metro Line 1 – Red'])
        dtype = random.choice(['Signal failure','Track obstruction','Mechanical fault','Power outage'])
        rows = [('Incident ID:', inc_id), ('Passenger:', name), ('Date:', date),
                ('Service Line:', line), ('Disruption Type:', dtype),
                ('Estimated Delay:', f"{random.choice([45,60,75,90])} minutes")]
        for i,(label,val) in enumerate(rows):
            y = 192 + i*38
            d.text((35,y), label, fill='#78350f')
            d.text((230,y), val, fill='#0f172a')
        d.rectangle([35,430,865,488], fill='#fef3c7')
        d.rectangle([35,430,41,488], fill='#f59e0b')
        d.text((56,442), 'Confirms the passenger was affected by a verified service disruption.', fill='#78350f')
        d.text((56,466), 'Issued for official use upon request. Keep for your records.', fill='#78350f')
        d.rectangle([0,610,900,660], fill='#fef3c7')
        d.text((35,630), f'Ref: {ref}  |  Issued: {date}  |  Valid 48 hours', fill='#92400e')

    def _technical(self, d, img, name, org, date, ref, scenario):
        d.rectangle([0,0,900,660], fill='#0f172a')
        d.rectangle([0,0,900,115], fill='#111827')
        d.rectangle([0,115,900,122], fill='#22d3ee')
        d.text((35,22), 'TECHNICAL INCIDENT REPORT', fill='#f1f5f9')
        d.text((35,68), 'IT Operations — System Status Certificate', fill='#94a3b8')
        for y in range(130, 605, 22):
            d.rectangle([0,y,900,y+1], fill='#1e293b')
        d.text((35,148), 'VERIFIED SYSTEM INCIDENT', fill='#22d3ee')
        ticket = f"TKT-{random.randint(100000,999999)}"
        sys_name = random.choice(['VPN Gateway','Internal Network','Email Server','Remote Desktop'])
        rows = [('Ticket #:', ticket), ('Affected User:', name), ('Date/Time:', f"{date} {datetime.now().strftime('%H:%M')}"),
                ('System:', sys_name)]
        for i,(label,val) in enumerate(rows):
            y = 180 + i*38
            d.text((35,y), label, fill='#64748b'); d.text((230,y), val, fill='#f1f5f9')
        d.text((35,340), 'Severity:', fill='#64748b')
        d.rectangle([225,333,310,358], fill='#dc2626'); d.text((232,338), 'CRITICAL', fill='white')
        d.text((35,375), 'Status:', fill='#64748b')
        d.rectangle([225,368,320,393], fill='#b45309'); d.text((232,373), 'IN PROGRESS', fill='white')
        d.rectangle([35,415,865,472], fill='#1e293b')
        d.rectangle([35,415,41,472], fill='#22d3ee')
        d.text((56,428), 'User confirmed unable to access systems during this period.', fill='#94a3b8')
        d.text((56,452), 'IT Operations verified outage. Case number valid for audit trail.', fill='#94a3b8')
        d.rectangle([660,490,865,580], outline='#22d3ee', width=1)
        d.text((672,505), 'IT OPS VERIFIED', fill='#22d3ee'); d.text((672,535), f'Auth: {random.randint(1000,9999)}', fill='#64748b')
        d.rectangle([0,610,900,660], fill='#111827')
        d.text((35,630), f'Ref: {ref}  |  Issued: {date}  |  Valid 48 hrs', fill='#475569')

    def _generic(self, d, img, name, org, date, ref, scenario):
        d.rectangle([0,0,900,660], fill='#f8fafc')
        d.rectangle([0,0,900,115], fill='#4f46e5')
        d.rectangle([0,115,900,122], fill='#818cf8')
        d.text((35,22), f'{scenario.upper()} — VERIFICATION LETTER', fill='white')
        d.text((35,68), 'Official Document — Retain for your records', fill='#c7d2fe')
        d.text((35,145), f'Issued to: {name}', fill='#0f172a')
        d.text((35,182), f'Date: {date}', fill='#64748b')
        d.text((35,218), f'Reference: {ref}', fill='#64748b')
        d.rectangle([35,260,865,360], fill='#eef2ff')
        d.rectangle([35,260,41,360], fill='#4f46e5')
        d.text((56,278), f'This letter verifies that the above-named individual had a legitimate', fill='#3730a3')
        d.text((56,312), f'{scenario}-related obligation on the stated date.', fill='#3730a3')
        d.text((56,342), 'Issued for informational and verification purposes only.', fill='#3730a3')
        d.rectangle([0,610,900,660], fill='#eef2ff')
        d.text((35,630), f'Ref: {ref}  |  Issued: {date}  |  Valid 48 hours', fill='#6366f1')


# ── Instantiate ──────────────────────────────────────────────────────────────

excuse_gen  = ExcuseGenerator()
email_gen   = EmailGenerator()
apology_gen = ApologyGenerator()
emergency   = EmergencySystem()
proof_gen   = ProofGenerator()


# ── Auth Routes ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email    = request.form['email']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error'); return redirect(url_for('register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error'); return redirect(url_for('register'))
        db.session.add(User(username=username, email=email, password_hash=generate_password_hash(password)))
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form['username']).first()
        if user and check_password_hash(user.password_hash, request.form['password']):
            login_user(user); return redirect(url_for('dashboard'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    recent   = Excuse.query.filter_by(user_id=current_user.id).order_by(Excuse.created_at.desc()).limit(8).all()
    contacts = EmergencyContact.query.filter_by(user_id=current_user.id).all()
    total    = Excuse.query.filter_by(user_id=current_user.id).count()
    favs     = Excuse.query.filter_by(user_id=current_user.id, is_favorite=True).count()
    now = datetime.now()
    return render_template('dashboard.html', excuses=recent, contacts=contacts,
                           total_excuses=total, fav_count=favs, now=now)


# ── API Routes ────────────────────────────────────────────────────────────────

@app.route('/api/generate_excuse', methods=['POST'])
@login_required
def api_generate_excuse():
    d = request.get_json()
    excuse = excuse_gen.generate(d.get('scenario','work'), d.get('urgency','medium'),
                                 d.get('language','en'), d.get('custom_context',''))
    rec = Excuse(content=excuse, scenario=d.get('scenario','work'), urgency=d.get('urgency','medium'),
                 language=d.get('language','en'), user_id=current_user.id)
    db.session.add(rec); db.session.commit()
    return jsonify({'excuse': excuse, 'id': rec.id})

@app.route('/api/generate_email', methods=['POST'])
@login_required
def api_generate_email():
    d = request.get_json()
    result = email_gen.generate(d.get('recipient_type','boss'), d.get('tone','professional'),
                                d.get('excuse',''), d.get('sender_name', current_user.username),
                                d.get('recipient_name','Sir/Madam'), d.get('context',''),
                                d.get('language', 'en'))
    return jsonify(result)

@app.route('/api/generate_apology', methods=['POST'])
@login_required
def api_generate_apology():
    d = request.get_json()
    text = apology_gen.generate(d.get('style','professional'), d.get('context',''), d.get('language','en'))
    return jsonify({'apology': text})

@app.route('/api/generate_proof', methods=['POST'])
@login_required
def api_generate_proof():
    d   = request.get_json()
    img = proof_gen.generate(d.get('proof_type','generic'), d.get('scenario','work'),
                             d.get('custom_name', current_user.username),
                             d.get('custom_org',''), d.get('excuse_text',''))
    return jsonify({'proof_image': img})

@app.route('/api/trigger_emergency', methods=['POST'])
@login_required
def api_trigger_emergency():
    d = request.get_json()
    return jsonify(emergency.trigger(d.get('scenario','family_emergency'),
                                     d.get('contact_name','Contact'),
                                     d.get('contact_phone',''), d.get('mode','sms')))

@app.route('/api/emergency_scenarios')
@login_required
def api_emergency_scenarios():
    return jsonify(emergency.get_scenarios())

@app.route('/api/save_contact', methods=['POST'])
@login_required
def api_save_contact():
    d = request.get_json()
    phone = d.get('phone','').strip()
    if EmergencyContact.query.filter_by(user_id=current_user.id, phone=phone).first():
        return jsonify({'success': False, 'message': 'Contact already saved.'})
    c = EmergencyContact(user_id=current_user.id, name=d.get('name','').strip(),
                         phone=phone, relationship=d.get('relationship','Friend').strip())
    db.session.add(c); db.session.commit()
    return jsonify({'success': True, 'id': c.id, 'message': 'Contact saved!'})

@app.route('/api/get_contacts')
@login_required
def api_get_contacts():
    return jsonify([{'id':c.id,'name':c.name,'phone':c.phone,'relationship':c.relationship}
                    for c in EmergencyContact.query.filter_by(user_id=current_user.id).all()])

@app.route('/api/delete_contact/<int:cid>', methods=['DELETE'])
@login_required
def api_delete_contact(cid):
    c = EmergencyContact.query.get(cid)
    if c and c.user_id == current_user.id:
        db.session.delete(c); db.session.commit(); return jsonify({'success': True})
    return jsonify({'success': False})

@app.route('/api/get_history')
@login_required
def api_get_history():
    excuses = Excuse.query.filter_by(user_id=current_user.id).order_by(Excuse.created_at.desc()).all()
    return jsonify([{'id':e.id,'content':e.content,'scenario':e.scenario,'urgency':e.urgency,
                     'language':e.language,'created_at':e.created_at.strftime('%b %d %H:%M'),
                     'effectiveness_score':e.effectiveness_score,'is_favorite':e.is_favorite} for e in excuses])

@app.route('/api/toggle_favorite', methods=['POST'])
@login_required
def api_toggle_favorite():
    d = request.get_json()
    exc = Excuse.query.get(d.get('excuse_id'))
    if exc and exc.user_id == current_user.id:
        exc.is_favorite = not exc.is_favorite; db.session.commit()
        return jsonify({'success': True, 'is_favorite': exc.is_favorite})
    return jsonify({'success': False})

@app.route('/api/rate_excuse', methods=['POST'])
@login_required
def api_rate_excuse():
    d = request.get_json()
    exc = Excuse.query.get(d.get('excuse_id'))
    if exc and exc.user_id == current_user.id:
        exc.effectiveness_score = d.get('rating', 0); db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
