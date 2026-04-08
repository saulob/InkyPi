import random
import logging
from datetime import datetime
from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

TWEMOJI_BASE_URL = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/svg"


def _emoji_to_twemoji_url(emoji):
    """Convert a Unicode emoji string to a Twemoji CDN SVG URL."""
    codepoints = "-".join(
        f"{ord(c):x}" for c in emoji if ord(c) != 0xFE0F
    )
    return f"{TWEMOJI_BASE_URL}/{codepoints}.svg"


def _get_smart_mood():
    """Select a mood based on current time and day of week with weighted probabilities.
    
    Returns a dict with:
    - mood: selected mood key
    - time_period: morning/afternoon/evening/night
    - weekday_name: Monday/Tuesday/etc
    - selected_weight: weight value of chosen mood
    """
    now = datetime.now()
    hour = now.hour
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    
    # For late night hours (00:00-04:59), use previous day for weekday-based weighting
    # to make mood selection feel more natural for late night usage
    if hour < 5:
        weekday = (weekday - 1) % 7
    
    weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    weekday_name = weekday_names[weekday]
    
    # Determine time period
    if 5 <= hour < 12:
        time_period = "morning"
    elif 12 <= hour < 17:
        time_period = "afternoon"
    elif 17 <= hour < 21:
        time_period = "evening"
    else:
        time_period = "night"
    
    # Base weight of 1 for all moods
    mood_weights = {
        "happy": 1,
        "neutral": 1,
        "low_energy": 1,
        "stress": 1,
        "fun": 1,
        "weird": 1,
        "focus": 1,
        "adventure": 1,
        "love": 1,
        "sick": 1,
    }
    
    # Incrementally adjust weights based on time period (+1 or +2)
    if time_period == "morning":
        mood_weights["focus"] += 2
        mood_weights["happy"] += 1
        mood_weights["neutral"] += 1
    elif time_period == "afternoon":
        mood_weights["focus"] += 2
        mood_weights["neutral"] += 1
        mood_weights["stress"] += 1
    elif time_period == "evening":
        mood_weights["fun"] += 2
        mood_weights["love"] += 1
        mood_weights["low_energy"] += 1
    else:  # night
        mood_weights["low_energy"] += 2
        mood_weights["weird"] += 1
        mood_weights["neutral"] += 1
    
    # Incrementally adjust weights based on weekday (+1 or +2)
    # For late night (00:00-04:59), weekday is already adjusted to previous day above
    if weekday == 0:  # Monday
        mood_weights["focus"] += 2
        mood_weights["stress"] += 1
    elif weekday == 4:  # Friday
        mood_weights["happy"] += 2
        mood_weights["fun"] += 1
    elif weekday == 5:  # Saturday
        mood_weights["fun"] += 2
        mood_weights["adventure"] += 1
        mood_weights["love"] += 1
    elif weekday == 6:  # Sunday
        mood_weights["low_energy"] += 1
        mood_weights["love"] += 1
        mood_weights["neutral"] += 1
    
    # Small random boost for all moods to keep variety and avoid rigid patterns
    for mood in mood_weights:
        mood_weights[mood] += random.random() * 0.3
    
    # Select mood using weighted random choice
    moods = list(mood_weights.keys())
    weights = [mood_weights[mood] for mood in moods]
    selected_mood = random.choices(moods, weights=weights, k=1)[0]
    selected_weight = mood_weights[selected_mood]
    
    return {
        "mood": selected_mood,
        "time_period": time_period,
        "weekday_name": weekday_name,
        "selected_weight": round(selected_weight, 1),
    }

MOOD_DATA = {
    "happy": {
        "emojis": [
            "😀", "😃", "😄", "😁", "😆", "😅", "🙂", "😊", "😇", "🥳",
        ],
        "captions": [
            "Good vibes today",
            "Feeling bright",
            "A cheerful moment",
            "Smile mode on",
            "Everything feels right",
            "Light and easy day",
            "Positive energy",
            "Keep smiling",
            "Good mood activated",
            "Today is a good day",
        ],
    },
    "neutral": {
        "emojis": [
            "🙂", "😐", "😶", "😑", "🤔", "🧐", "🤓", "😌", "🙄", "😏",
        ],
        "captions": [
            "Just cruising",
            "Steady and calm",
            "Nothing dramatic today",
            "Balanced mood",
            "Taking it easy",
            "All good, no rush",
            "Simple day ahead",
            "Calm and collected",
            "Neutral vibes",
            "Going with the flow",
        ],
    },
    "low_energy": {
        "emojis": [
            "😴", "😪", "😌", "😔", "😕", "😞", "😟", "😓", "😥", "🫠",
        ],
        "captions": [
            "Take it slow",
            "Quiet energy today",
            "Easy pace",
            "Recharge mode",
            "Low battery vibes",
            "Rest a bit more",
            "Slow but steady",
            "Take a break",
            "Energy saving mode",
            "Just getting through",
        ],
    },
    "stress": {
        "emojis": [
            "😤", "😠", "😡", "😣", "😖", "😫", "😩", "🤯", "😵", "😵‍💫",
        ],
        "captions": [
            "A lot going on",
            "Take a breath",
            "Messy but moving",
            "One step at a time",
            "Too much today",
            "Keep pushing",
            "Stay strong",
            "Breathe and focus",
            "Handling chaos",
            "Survive and move",
        ],
    },
    "fun": {
        "emojis": [
            "🎮", "🎲", "🎉", "🎈", "🍕", "🍔", "🌭", "🍟", "🎬", "🎥",
        ],
        "captions": [
            "Time to have fun",
            "Play mode on",
            "Enjoy the moment",
            "Just for fun",
            "Take a break and play",
            "Good time ahead",
            "Relax and enjoy",
            "Fun vibes only",
            "Let loose a bit",
            "Today is for fun",
        ],
    },
    "weird": {
        "emojis": [
            "🤡", "👽", "👻", "💀", "👹", "👺", "🤖", "👾", "🥸", "💩",
        ],
        "captions": [
            "Feeling weird today",
            "Something is off",
            "Strange vibes",
            "Not a normal day",
            "Embrace the chaos",
            "A bit unusual",
            "Weird but okay",
            "Glitch in the mood",
            "Unexpected energy",
            "Just roll with it",
        ],
    },
    "sick": {
        "emojis": [
            "🤢", "🤮", "😷", "🤒", "🤕", "🥴", "😵", "🤧", "🥶", "🥵",
        ],
        "captions": [
            "Not feeling great",
            "Take care today",
            "Rest and recover",
            "Slow down and heal",
            "Body needs a break",
            "Easy day today",
            "Take it easy",
            "Recovery mode",
            "Be gentle with yourself",
            "Time to rest",
        ],
    },
    "focus": {
        "emojis": [
            "🤓", "🧐", "💻", "📈", "🎯", "🚀", "🧠", "🕹️", "⏳", "📊",
        ],
        "captions": [
            "Focus mode on",
            "Time to get things done",
            "Locked in",
            "Deep work time",
            "Stay sharp",
            "No distractions",
            "Get in the zone",
            "Productive day ahead",
            "Eyes on the goal",
            "Let’s build something",
        ],
    },
    "adventure": {
        "emojis": [
            "✈️", "🌍", "🌞", "🚀", "🗺️", "🎒", "🏝️", "🌄", "🌌", "🧭",
        ],
        "captions": [
            "Ready for adventure",
            "Explore something new",
            "Let’s go somewhere",
            "New horizons today",
            "Break the routine",
            "Adventure awaits",
            "Time to explore",
            "Go beyond",
            "Try something different",
            "See the world",
        ],
    },
    "love": {
        "emojis": [
            "❤️", "💖", "💘", "💞", "🥰", "😍", "😘", "😽", "💕", "❤️‍🔥",
        ],
        "captions": [
            "Love is in the air",
            "Feeling the love",
            "Heart full today",
            "Spread some love",
            "Warm and happy",
            "Sweet vibes",
            "Love mode on",
            "All about love",
            "Good feelings inside",
            "Share the love",
        ],
    },
}

# Caption translations per language. Only captions are translated; debug info remains English.
# Languages supported including Brazilian Portuguese variant: de, en, es, fr, id, it, nl, pt, pt-br
ENGLISH_CAPTIONS = {k: v["captions"] for k, v in MOOD_DATA.items()}

CAPTION_TRANSLATIONS = {
    "en": ENGLISH_CAPTIONS,
    "pt": {
        "happy": [
            "Boas vibrações hoje",
            "Sinto-me radiante",
            "Um momento alegre",
            "Modo sorriso ativado",
            "Tudo parece certo",
            "Dia leve e tranquilo",
            "Energia positiva",
            "Continue a sorrir",
            "Bom humor ativado",
            "Hoje é um bom dia",
        ],
        "neutral": [
            "Só a seguir o ritmo",
            "Calmo e estável",
            "Nada de dramático hoje",
            "Humor equilibrado",
            "A levar de forma leve",
            "Tudo bem, sem pressa",
            "Dia simples pela frente",
            "Calmo e sereno",
            "Vibrações neutras",
            "Ao ritmo do dia",
        ],
        "low_energy": [
            "Vai devagar",
            "Energia baixa hoje",
            "Ritmo tranquilo",
            "Modo recarregar",
            "Vibrações de baixa bateria",
            "Descanse um pouco mais",
            "Devagar, mas firme",
            "Faça uma pausa",
            "Modo economia de energia",
            "A seguir com calma",
        ],
        "stress": [
            "Muita coisa a acontecer",
            "Respire fundo",
            "Tudo desorganizado, mas a andar",
            "Um passo de cada vez",
            "Demasiado hoje",
            "Continue a insistir",
            "Mantenha-se forte",
            "Respire e concentre-se",
            "Lidando com o caos",
            "Sobreviva e siga",
        ],
        "fun": [
            "Hora de se divertir",
            "Modo diversão ativado",
            "Aproveite o momento",
            "Só pela diversão",
            "Faça uma pausa e brinque",
            "Bons momentos pela frente",
            "Relaxe e aproveite",
            "Apenas vibrações divertidas",
            "Descontraia um pouco",
            "Hoje é para se divertir",
        ],
        "weird": [
            "Sinto-me estranho hoje",
            "Tem algo errado",
            "Vibrações estranhas",
            "Dia nada normal",
            "Abrace o caos",
            "Um pouco invulgar",
            "Estranho, mas tudo bem",
            "Humor bugado",
            "Energia inesperada",
            "Apenas siga o fluxo",
        ],
        "sick": [
            "Não me sinto bem",
            "Cuide-se hoje",
            "Descanse e recupere",
            "Vá com calma e recupere",
            "O corpo precisa de um tempo",
            "Dia tranquilo hoje",
            "Vá com calma",
            "Modo recuperação",
            "Seja gentil consigo mesmo",
            "Hora de descansar",
        ],
        "focus": [
            "Modo foco ativado",
            "Hora de fazer acontecer",
            "Concentrado",
            "Tempo de trabalho profundo",
            "Mantenha-se afiado",
            "Sem distrações",
            "Entre na zona",
            "Dia produtivo à frente",
            "Olhos no objetivo",
            "Vamos construir algo",
        ],
        "adventure": [
            "Pronto para a aventura",
            "Explore algo novo",
            "Vamos para algum lugar",
            "Novos horizontes hoje",
            "Quebre a rotina",
            "Aventura aguarda",
            "Hora de explorar",
            "Vá além",
            "Tente algo diferente",
            "Veja o mundo",
        ],
        "love": [
            "O amor está no ar",
            "Sentindo o amor",
            "Coração cheio hoje",
            "Espalhe um pouco de amor",
            "Aconchegante e feliz",
            "Vibrações doces",
            "Modo amor ativado",
            "Tudo sobre amor",
            "Bons sentimentos por dentro",
            "Compartilhe o amor",
        ],
    },
    "pt-br": {
        "happy": [
            "Boas vibrações hoje",
            "Me sentindo radiante",
            "Um momento alegre",
            "Modo sorriso ativado",
            "Tudo parece certo",
            "Dia leve e tranquilo",
            "Energia positiva",
            "Continue sorrindo",
            "Bom humor ativado",
            "Hoje é um bom dia",
        ],
        "neutral": [
            "Levando numa boa",
            "Tranquilo e calmo",
            "Nada dramático hoje",
            "Humor equilibrado",
            "Relaxando",
            "Tudo bem, sem pressa",
            "Um dia simples pela frente",
            "Calmo e sereno",
            "Vibrações neutras",
            "Deixando a vida fluir",
        ],
        "low_energy": [
            "Vai com calma",
            "Energia baixa hoje",
            "Ritmo tranquilo",
            "Modo recarga",
            "Bateria fraca",
            "Descanse um pouco mais",
            "Devagar e sempre",
            "Faça uma pausa",
            "Modo economia de energia",
            "Apenas sobrevivendo",
        ],
        "stress": [
            "Muita coisa acontecendo",
            "Respire fundo",
            "Tudo meio bagunçado, mas indo",
            "Um passo de cada vez",
            "Tá pesado hoje",
            "Continue em frente",
            "Mantenha-se forte",
            "Respire e concentre-se",
            "Lidando com o caos",
            "Sobreviva e siga em frente",
        ],
        "fun": [
            "Hora de se divertir",
            "Modo diversão ativado",
            "Aproveite o momento",
            "Só pela diversão",
            "Faça uma pausa e brinque",
            "Bons momentos à frente",
            "Relaxe e aproveite",
            "Só boas vibrações",
            "Solte-se um pouco",
            "Hoje é para se divertir",
        ],
        "weird": [
            "Me sentindo estranho hoje",
            "Algo está errado",
            "Vibrações estranhas",
            "Dia nada normal",
            "Abrace o caos",
            "Um pouco incomum",
            "Estranho, mas tudo bem",
            "Mudança de humor",
            "Energia inesperada",
            "Só deixa rolar",
        ],
        "sick": [
            "Não me sinto bem",
            "Cuide-se hoje",
            "Descanse e recupere",
            "Vai com calma e se recupere",
            "O corpo precisa de uma pausa",
            "Dia tranquilo hoje",
            "Vá com calma",
            "Modo recuperação",
            "Seja gentil consigo mesmo",
            "Hora de descansar",
        ],
        "focus": [
            "Modo foco ativado",
            "Hora de fazer acontecer",
            "Concentrado",
            "Tempo de trabalho profundo",
            "Mantenha-se afiado",
            "Sem distrações",
            "Entre no ritmo",
            "Dia produtivo pela frente",
            "Olhos no objetivo",
            "Vamos construir algo",
        ],
        "adventure": [
            "Pronto para a aventura",
            "Explore algo novo",
            "Vamos para algum lugar",
            "Novos horizontes hoje",
            "Quebre a rotina",
            "A aventura espera por você",
            "Hora de explorar",
            "Vá além",
            "Tente algo diferente",
            "Veja o mundo",
        ],
        "love": [
            "O amor está no ar",
            "Sentindo o amor",
            "Coração cheio hoje",
            "Espalhe um pouco de amor",
            "Aconchegante e feliz",
            "Doces vibrações",
            "Modo amor ativado",
            "Tudo sobre amor",
            "Bons sentimentos por dentro",
            "Compartilhe o amor",
        ],
    },
    "es": {
        "happy": [
            "Buenas vibras hoy",
            "Me siento radiante",
            "Un momento alegre",
            "Modo sonrisa activado",
            "Todo se siente bien",
            "Día ligero y relajado",
            "Energía positiva",
            "Sigue sonriendo",
            "Buen estado de ánimo activado",
            "Hoy es un buen día",
        ],
        "neutral": [
            "Solo navegando",
            "Firme y tranquilo",
            "Nada dramático hoy",
            "Ánimo equilibrado",
            "Tomándolo con calma",
            "Todo bien, sin prisa",
            "Día simple por delante",
            "Calmado y sereno",
            "Vibras neutras",
            "Yendo con la corriente",
        ],
        "low_energy": [
            "Tómalo con calma",
            "Energía baja hoy",
            "Ritmo tranquilo",
            "Modo recargar",
            "Vibras de batería baja",
            "Descansa un poco más",
            "Lento pero constante",
            "Tómate un descanso",
            "Modo ahorro de energía",
            "Solo pasando el día",
        ],
        "stress": [
            "Mucho pasando",
            "Respira profundo",
            "Desordenado pero en movimiento",
            "Un paso a la vez",
            "Demasiado hoy",
            "Sigue adelante",
            "Mantente fuerte",
            "Respira y concéntrate",
            "Manejando el caos",
            "Sobrevive y sigue",
        ],
        "fun": [
            "Hora de divertirse",
            "Modo juego activado",
            "Disfruta el momento",
            "Solo por diversión",
            "Tómate un descanso y juega",
            "Buen tiempo por delante",
            "Relájate y disfruta",
            "Solo vibras divertidas",
            "Suéltate un poco",
            "Hoy es para divertirse",
        ],
        "weird": [
            "Sintiendo raro hoy",
            "Algo está fuera",
            "Vibras extrañas",
            "No es un día normal",
            "Abraza el caos",
            "Un poco inusual",
            "Raro pero está bien",
            "Fallo en el humor",
            "Energía inesperada",
            "Sigue adelante",
        ],
        "sick": [
            "No me siento bien",
            "Cuídate hoy",
            "Descansa y recupérate",
            "Baja el ritmo y sana",
            "El cuerpo necesita un descanso",
            "Día tranquilo hoy",
            "Tómatelo con calma",
            "Modo recuperación",
            "Sé amable contigo mismo",
            "Hora de descansar",
        ],
        "focus": [
            "Modo foco activado",
            "Hora de hacer las cosas",
            "Enfocado",
            "Tiempo de trabajo profundo",
            "Mantente afilado",
            "Sin distracciones",
            "Entra en la zona",
            "Día productivo por delante",
            "Ojos en la meta",
            "Construyamos algo",
        ],
        "adventure": [
            "Listo para la aventura",
            "Explora algo nuevo",
            "Vamos a algún lugar",
            "Nuevos horizontes hoy",
            "Rompe la rutina",
            "La aventura espera",
            "Hora de explorar",
            "Ve más allá",
            "Prueba algo diferente",
            "Ve el mundo",
        ],
        "love": [
            "El amor está en el aire",
            "Sintiendo el amor",
            "Corazón lleno hoy",
            "Comparte algo de amor",
            "Cálido y feliz",
            "Vibras dulces",
            "Modo amor activado",
            "Todo sobre el amor",
            "Buenos sentimientos por dentro",
            "Comparte el amor",
        ],
    },
    "fr": {
        "happy": [
            "Bonnes vibrations aujourd'hui",
            "Se sentir rayonnant",
            "Un moment joyeux",
            "Mode sourire activé",
            "Tout va bien",
            "Journée légère et facile",
            "Énergie positive",
            "Continuez à sourire",
            "Bonne humeur activée",
            "Aujourd'hui est une bonne journée",
        ],
        "neutral": [
            "Juste tranquille",
            "Stable et calme",
            "Rien de dramatique aujourd'hui",
            "Humeur équilibrée",
            "Prendre les choses doucement",
            "Tout va bien, pas de précipitation",
            "Journée simple à venir",
            "Calme et posé",
            "Vibrations neutres",
            "Suivre le courant",
        ],
        "low_energy": [
            "Prends ton temps",
            "Énergie calme aujourd'hui",
            "Rythme facile",
            "Mode recharge",
            "Vibes batterie faible",
            "Repose-toi un peu plus",
            "Lent mais régulier",
            "Fais une pause",
            "Mode économie d'énergie",
            "Juste pour tenir",
        ],
        "stress": [
            "Beaucoup en cours",
            "Respire un coup",
            "Désordonné mais en mouvement",
            "Un pas à la fois",
            "Trop aujourd'hui",
            "Continue d'avancer",
            "Reste fort",
            "Respire et concentre-toi",
            "Gérer le chaos",
            "Survivre et avancer",
        ],
        "fun": [
            "Temps pour s'amuser",
            "Mode jeu activé",
            "Profite du moment",
            "Juste pour le plaisir",
            "Fais une pause et joue",
            "Bon moment à venir",
            "Détends-toi et profite",
            "Vibes amusantes seulement",
            "Lâche-toi un peu",
            "Aujourd'hui c'est pour s'amuser",
        ],
        "weird": [
            "Se sent étrange aujourd'hui",
            "Quelque chose cloche",
            "Vibes étranges",
            "Pas un jour normal",
            "Embrasse le chaos",
            "Un peu inhabituel",
            "Étrange mais ça va",
            "Bug dans l'humeur",
            "Énergie inattendue",
            "Suis le courant",
        ],
        "sick": [
            "Pas en forme",
            "Prends soin de toi aujourd'hui",
            "Repose-toi et récupère",
            "Ralentis et guéris",
            "Le corps a besoin d'une pause",
            "Jour tranquille aujourd'hui",
            "Prends-le doucement",
            "Mode récupération",
            "Sois doux avec toi-même",
            "Temps de repos",
        ],
        "focus": [
            "Mode concentration activé",
            "Temps de faire les choses",
            "Concentré",
            "Temps de travail profond",
            "Reste affûté",
            "Pas de distractions",
            "Entre dans la zone",
            "Journée productive à venir",
            "Les yeux sur l'objectif",
            "Construisons quelque chose",
        ],
        "adventure": [
            "Prêt pour l'aventure",
            "Explore quelque chose de nouveau",
            "Allons quelque part",
            "Nouveaux horizons aujourd'hui",
            "Brise la routine",
            "L'aventure attend",
            "Temps d'explorer",
            "Allez au-delà",
            "Essayez quelque chose de différent",
            "Voyez le monde",
        ],
        "love": [
            "L'amour est dans l'air",
            "Sentir l'amour",
            "Cœur rempli aujourd'hui",
            "Partagez un peu d'amour",
            "Chaud et heureux",
            "Vibes douces",
            "Mode amour activé",
            "Tout sur l'amour",
            "Bons sentiments à l'intérieur",
            "Partagez l'amour",
        ],
    },
    "de": {
        "happy": [
            "Gute Vibes heute",
            "Fühlt sich strahlend an",
            "Ein fröhlicher Moment",
            "Lächelmodus eingeschaltet",
            "Alles fühlt sich richtig an",
            "Leichter und entspannter Tag",
            "Positive Energie",
            "Weiter lächeln",
            "Gute Laune aktiviert",
            "Heute ist ein guter Tag",
        ],
        "neutral": [
            "Einfach unterwegs",
            "Ruhig und beständig",
            "Nichts Dramatisches heute",
            "Ausgeglichene Stimmung",
            "Nimmt es gelassen",
            "Alles gut, kein Stress",
            "Einfacher Tag voraus",
            "Ruhig und gesammelt",
            "Neutrale Vibes",
            "Mit dem Strom gehen",
        ],
        "low_energy": [
            "Nimm's langsam",
            "Leise Energie heute",
            "Gemäßigtes Tempo",
            "Aufladen-Modus",
            "Niedriger Akku-Vibe",
            "Ruh dich etwas mehr aus",
            "Langsam aber stetig",
            "Mach eine Pause",
            "Energiesparmodus",
            "Kommt irgendwie durch",
        ],
        "stress": [
            "Viel los",
            "Atme tief durch",
            "Chaotisch, aber vorwärts",
            "Ein Schritt nach dem anderen",
            "Zu viel heute",
            "Weiter durchziehen",
            "Bleib stark",
            "Atme und konzentriere dich",
            "Bewältige das Chaos",
            "Überleben und weiter",
        ],
        "fun": [
            "Zeit zum Spaß haben",
            "Spielmodus an",
            "Genieße den Moment",
            "Einfach zum Spaß",
            "Mach Pause und spiel",
            "Gute Zeiten voraus",
            "Entspann dich und genieße",
            "Nur Spaß-Vibes",
            "Lass locker",
            "Heute ist zum Spaß",
        ],
        "weird": [
            "Fühlt sich heute seltsam an",
            "Irgendetwas ist anders",
            "Seltsame Vibes",
            "Kein normaler Tag",
            "Umarme das Chaos",
            "Ein bisschen ungewöhnlich",
            "Seltsam, aber okay",
            "Stimmung spinnt",
            "Unerwartete Energie",
            "Einfach mitmachen",
        ],
        "sick": [
            "Fühle mich nicht gut",
            "Pass heute auf dich auf",
            "Ruhe und erhole dich",
            "Runterfahren und heilen",
            "Der Körper braucht Pause",
            "Ein ruhiger Tag heute",
            "Nimm es leicht",
            "Erholungsmodus",
            "Sei nett zu dir selbst",
            "Zeit zum Ausruhen",
        ],
        "focus": [
            "Fokusmodus an",
            "Zeit, Dinge zu erledigen",
            "Voll konzentriert",
            "Tiefenarbeitszeit",
            "Bleib scharf",
            "Keine Ablenkungen",
            "Komm in die Zone",
            "Produktiver Tag voraus",
            "Augen auf das Ziel",
            "Lass uns etwas bauen",
        ],
        "adventure": [
            "Bereit für Abenteuer",
            "Erkunde etwas Neues",
            "Lass uns irgendwohin gehen",
            "Neue Horizonte heute",
            "Durchbreche die Routine",
            "Abenteuer wartet",
            "Zeit zu erkunden",
            "Geh darüber hinaus",
            "Probiere etwas anderes",
            "Sieh die Welt",
        ],
        "love": [
            "Liebe liegt in der Luft",
            "Fühle die Liebe",
            "Herz heute voller",
            "Verteile etwas Liebe",
            "Warm und glücklich",
            "Süße Vibes",
            "Liebesmodus an",
            "Alles über Liebe",
            "Gute Gefühle drin",
            "Teile die Liebe",
        ],
    },
    "it": {
        "happy": [
            "Buone vibrazioni oggi",
            "Mi sento radioso",
            "Un momento allegro",
            "Modalità sorriso attivata",
            "Tutto sembra a posto",
            "Giornata leggera e facile",
            "Energia positiva",
            "Continua a sorridere",
            "Buon umore attivato",
            "Oggi è una buona giornata",
        ],
        "neutral": [
            "Solo in giro",
            "Stabile e calmo",
            "Niente di drammatico oggi",
            "Umore bilanciato",
            "Prendila con calma",
            "Tutto bene, niente fretta",
            "Giornata semplice davanti",
            "Calmo e raccolto",
            "Vibrazioni neutre",
            "Seguendo il flusso",
        ],
        "low_energy": [
            "Prendila con calma",
            "Energia bassa oggi",
            "Passo lento",
            "Modalità ricarica",
            "Vibrazioni batteria bassa",
            "Riposa un po' di più",
            "Lento ma costante",
            "Fai una pausa",
            "Modalità risparmio energetico",
            "Sto solo andando avanti",
        ],
        "stress": [
            "Molto in corso",
            "Fai un respiro",
            "Disordinato ma in movimento",
            "Un passo alla volta",
            "Troppo oggi",
            "Continua a spingere",
            "Rimani forte",
            "Respira e concentra",
            "Gestendo il caos",
            "Sopravvivi e vai avanti",
        ],
        "fun": [
            "Tempo per divertirsi",
            "Modalità gioco attiva",
            "Goditi il momento",
            "Solo per divertimento",
            "Prenditi una pausa e gioca",
            "Bel tempo avanti",
            "Rilassati e divertiti",
            "Solo vibrazioni divertenti",
            "Lasciati andare un po'",
            "Oggi è per divertirsi",
        ],
        "weird": [
            "Mi sento strano oggi",
            "Qualcosa non va",
            "Vibrazioni strane",
            "Non è un giorno normale",
            "Abbraccia il caos",
            "Un po' insolito",
            "Strano ma va bene",
            "Errore nell'umore",
            "Energia inaspettata",
            "Vai con il flusso",
        ],
        "sick": [
            "Non mi sento bene",
            "Abbi cura di te oggi",
            "Riposa e recupera",
            "Rallenta e guarisci",
            "Il corpo ha bisogno di una pausa",
            "Giornata facile oggi",
            "Prendila con calma",
            "Modalità recupero",
            "Sii gentile con te stesso",
            "È ora di riposare",
        ],
        "focus": [
            "Modalità concentrazione attiva",
            "È ora di fare le cose",
            "Concentrato",
            "Tempo di lavoro profondo",
            "Rimani affilato",
            "Nessuna distrazione",
            "Entra nella zona",
            "Giornata produttiva avanti",
            "Occhi sull'obiettivo",
            "Costruiamo qualcosa",
        ],
        "adventure": [
            "Pronto per l'avventura",
            "Esplora qualcosa di nuovo",
            "Andiamo da qualche parte",
            "Nuovi orizzonti oggi",
            "Rompi la routine",
            "L'avventura aspetta",
            "È ora di esplorare",
            "Vai oltre",
            "Prova qualcosa di diverso",
            "Vedi il mondo",
        ],
        "love": [
            "L'amore è nell'aria",
            "Sentendo l'amore",
            "Cuore pieno oggi",
            "Spargi un po' d'amore",
            "Caldo e felice",
            "Vibrazioni dolci",
            "Modalità amore attivata",
            "Tutto sull'amore",
            "Buoni sentimenti dentro",
            "Condividi l'amore",
        ],
    },
    "nl": {
        "happy": [
            "Goede vibes vandaag",
            "Voel me stralend",
            "Een vrolijk moment",
            "Glimlachmodus aan",
            "Alles voelt goed",
            "Lichte en makkelijke dag",
            "Positieve energie",
            "Blijf glimlachen",
            "Goed humeur geactiveerd",
            "Vandaag is een goede dag",
        ],
        "neutral": [
            "Gewoon cruisen",
            "Steady en rustig",
            "Niets dramatisch vandaag",
            "Gebalanceerde stemming",
            "Doe rustig aan",
            "Alles goed, geen haast",
            "Eenvoudige dag vooruit",
            "Kalm en beheerst",
            "Neutrale vibes",
            "Gaan met de stroom",
        ],
        "low_energy": [
            "Doe rustig aan",
            "Rustige energie vandaag",
            "Makkelijk tempo",
            "Oplaadmodus",
            "Laag batterijgevoel",
            "Rust nog even",
            "Langzaam maar zeker",
            "Neem een pauze",
            "Energiebesparingsmodus",
            "Gewoon doorgaan",
        ],
        "stress": [
            "Veel aan de hand",
            "Haal adem",
            "Chaotisch maar gaande",
            "Een stap tegelijk",
            "Te veel vandaag",
            "Blijf duwen",
            "Blijf sterk",
            "Adem en focus",
            "Omgaan met chaos",
            "Overleven en doorgaan",
        ],
        "fun": [
            "Tijd om plezier te hebben",
            "Speelmodus aan",
            "Geniet van het moment",
            "Gewoon voor de lol",
            "Neem een pauze en speel",
            "Leuke tijd vooruit",
            "Ontspan en geniet",
            "Alleen leuke vibes",
            "Laat los een beetje",
            "Vandaag is om te genieten",
        ],
        "weird": [
            "Voel me raar vandaag",
            "Iets is anders",
            "Vreemde vibes",
            "Geen normale dag",
            "Omarm de chaos",
            "Een beetje ongebruikelijk",
            "Raar maar oke",
            "Fout in de stemming",
            "Onverwachte energie",
            "Gewoon meebewegen",
        ],
        "sick": [
            "Voel me niet goed",
            "Zorg vandaag voor jezelf",
            "Rust en herstel",
            "Rust en genees",
            "Het lichaam heeft rust nodig",
            "Gemakkelijke dag vandaag",
            "Doe rustig aan",
            "Herstelmodus",
            "Wees lief voor jezelf",
            "Tijd om te rusten",
        ],
        "focus": [
            "Focusmodus aan",
            "Tijd om dingen te doen",
            "Gefocust",
            "Diep werk tijd",
            "Blijf scherp",
            "Geen afleidingen",
            "Ga de zone in",
            "Productieve dag vooruit",
            "Ogen op het doel",
            "Laten we iets bouwen",
        ],
        "adventure": [
            "Klaar voor avontuur",
            "Ontdek iets nieuws",
            "Laten we ergens heen gaan",
            "Nieuwe horizonten vandaag",
            "Doorbreek de routine",
            "Avontuur wacht",
            "Tijd om te verkennen",
            "Ga verder",
            "Probeer iets anders",
            "Zie de wereld",
        ],
        "love": [
            "Liefde hangt in de lucht",
            "Voel de liefde",
            "Hart vol vandaag",
            "Verspreid wat liefde",
            "Warm en gelukkig",
            "Zoete vibes",
            "Liefdesmodus aan",
            "Alles over liefde",
            "Goede gevoelens binnenin",
            "Deel de liefde",
        ],
    },
    "id": {
        "happy": [
            "Suasana baik hari ini",
            "Merasa cerah",
            "Momen yang ceria",
            "Mode senyum aktif",
            "Semuanya terasa benar",
            "Hari yang ringan dan mudah",
            "Energi positif",
            "Terus tersenyum",
            "Suasana hati baik aktif",
            "Hari ini adalah hari yang baik",
        ],
        "neutral": [
            "Hanya santai",
            "Stabil dan tenang",
            "Tidak ada yang dramatis hari ini",
            "Suasana seimbang",
            "Santai saja",
            "Semua baik, tidak terburu-buru",
            "Hari sederhana ke depan",
            "Tenang dan terkumpul",
            "Suasana netral",
            "Mengikuti arus",
        ],
        "low_energy": [
            "Jalankan perlahan",
            "Energi tenang hari ini",
            "Kecepatan mudah",
            "Mode isi ulang",
            "Suasana baterai rendah",
            "Istirahat sedikit lagi",
            "Lambat tapi mantap",
            "Istirahat sejenak",
            "Mode hemat energi",
            "Hanya bertahan",
        ],
        "stress": [
            "Banyak yang terjadi",
            "Tarik napas",
            "Berantakan tapi bergerak",
            "Satu langkah pada satu waktu",
            "Terlalu banyak hari ini",
            "Terus dorong",
            "Tetap kuat",
            "Tarik napas dan fokus",
            "Menghadapi kekacauan",
            "Bertahan dan maju",
        ],
        "fun": [
            "Waktunya bersenang-senang",
            "Mode main aktif",
            "Nikmati momen",
            "Hanya untuk bersenang-senang",
            "Istirahat dan bermain",
            "Waktu menyenangkan menanti",
            "Santai dan nikmati",
            "Hanya suasana menyenangkan",
            "Lepaskan sedikit",
            "Hari ini untuk bersenang-senang",
        ],
        "weird": [
            "Merasa aneh hari ini",
            "Ada yang tidak beres",
            "Suasana aneh",
            "Bukan hari normal",
            "Terima kekacauan",
            "Sedikit tidak biasa",
            "Aneh tapi oke",
            "Gangguan suasana",
            "Energi tak terduga",
            "Ikuti saja",
        ],
        "sick": [
            "Tidak merasa baik",
            "Jaga diri hari ini",
            "Istirahat dan pulih",
            "Lambat dan sembuh",
            "Tubuh butuh istirahat",
            "Hari mudah hari ini",
            "Santai saja",
            "Mode pemulihan",
            "Bersikap lembut pada diri sendiri",
            "Waktunya istirahat",
        ],
        "focus": [
            "Mode fokus aktif",
            "Waktunya menyelesaikan tugas",
            "Fokus penuh",
            "Waktu kerja mendalam",
            "Tetap tajam",
            "Tanpa gangguan",
            "Masuk ke zona",
            "Hari produktif menanti",
            "Mata pada tujuan",
            "Mari bangun sesuatu",
        ],
        "adventure": [
            "Siap berpetualang",
            "Jelajahi sesuatu yang baru",
            "Mari pergi ke suatu tempat",
            "Cakrawala baru hari ini",
            "Hancurkan rutinitas",
            "Petualangan menanti",
            "Waktunya menjelajah",
            "Pergi lebih jauh",
            "Coba sesuatu yang berbeda",
            "Lihat dunia",
        ],
        "love": [
            "Cinta ada di udara",
            "Merasa cinta",
            "Hati penuh hari ini",
            "Sebarkan sedikit cinta",
            "Hangat dan bahagia",
            "Suasana manis",
            "Mode cinta aktif",
            "Semua tentang cinta",
            "Perasaan baik di dalam",
            "Bagikan cinta",
        ],
    },
}


class EmojiMood(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params['style_settings'] = True
        return template_params

    def generate_image(self, settings, device_config):
        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        # Determine selected mood from plugin settings.
        selected_mood_value = None
        if isinstance(settings, dict):
            selected_mood_value = settings.get("mood")
        if not selected_mood_value:
            selected_mood_value = "random"

        selected_mood_key = str(selected_mood_value).lower()

        # Determine the final mood key.
        if selected_mood_key == "random":
            mood_key = random.choice(list(MOOD_DATA.keys()))
        elif selected_mood_key == "smart":
            mood_key = _get_smart_mood()["mood"]
        else:
            mood_key = selected_mood_key if selected_mood_key in MOOD_DATA else random.choice(list(MOOD_DATA.keys()))

        mood = MOOD_DATA[mood_key]
        emoji = random.choice(mood["emojis"])

        # Determine selected language (default 'en') and pick a translated caption list for the mood
        language = "en"
        if isinstance(settings, dict):
            language = str(settings.get("language") or "en").lower()

        captions_for_mood = CAPTION_TRANSLATIONS.get(language, CAPTION_TRANSLATIONS["en"]).get(mood_key, MOOD_DATA[mood_key]["captions"])
        caption = random.choice(captions_for_mood)

        # Show caption: strict true/false setting
        show_caption = True
        if isinstance(settings, dict):
            show_caption_value = str(settings.get("showCaption") or "true").lower()
            show_caption = show_caption_value == "true"

        template_params = {
            "emoji": emoji,
            "twemoji_url": _emoji_to_twemoji_url(emoji),
            "caption": caption,
            "plugin_settings": settings,
            "show_caption": show_caption,
        }

        image = self.render_image(
            dimensions, "emoji_mood.html", "emoji_mood.css", template_params
        )
        return image
