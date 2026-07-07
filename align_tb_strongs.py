#!/usr/bin/env python3
"""Embed Strong's tags into TB (Indonesian) Old Testament text.

Strategy:
  For each verse, align KJV words (with Strong's tags) to TB words
  using a small hand-curated bilingual dictionary + positional proximity.
"""

import os
import re
import sqlite3
import sys
from collections import defaultdict

DB_PATH = os.path.join(os.path.dirname(__file__), "bible_strong.db")

OT_BOOKS = [
    "Gen","Exod","Lev","Num","Deut","Josh","Judg","Ruth",
    "1Sam","2Sam","1Kgs","2Kgs","1Chr","2Chr","Ezra","Neh",
    "Esth","Job","Ps","Prov","Eccl","Song","Isa","Jer","Lam",
    "Ezek","Dan","Hos","Joel","Amos","Obad","Jonah","Mic",
    "Nah","Hab","Zeph","Hag","Zech","Mal",
]

# ── Bilingual dictionary: English → Indonesian ──────────────────────────
# Only high-confidence pairs. First entry is the preferred translation.
BILINGUAL = {
    # Most common Bible terms (~200 headwords)
    "lord": ["tuhan"],
    "god": ["allah"],
    "king": ["raja"],
    "son": ["anak", "putera", "bin"],
    "day": ["hari"],
    "house": ["rumah"],
    "hand": ["tangan"],
    "heaven": ["langit"],
    "heavens": ["langit"],
    "earth": ["bumi", "tanah", "negeri"],
    "land": ["negeri", "tanah"],
    "water": ["air"],
    "fire": ["api"],
    "mountain": ["gunung"],
    "sea": ["laut"],
    "word": ["firman", "perkataan"],
    "name": ["nama"],
    "father": ["bapa"],
    "mother": ["ibu"],
    "brother": ["saudara"],
    "sister": ["saudara"],
    "servant": ["hamba"],
    "priest": ["imam"],
    "prophet": ["nabi"],
    "altar": ["mezbah"],
    "sacrifice": ["korban"],
    "offering": ["persembahan"],
    "law": ["hukum", "taurat"],
    "commandment": ["perintah"],
    "covenant": ["perjanjian"],
    "sabbath": ["sabat"],
    "spirit": ["roh"],
    "soul": ["jiwa"],
    "heart": ["hati"],
    "flesh": ["daging"],
    "blood": ["darah"],
    "bone": ["tulang"],
    "eye": ["mata"],
    "eyes": ["mata"],
    "ear": ["telinga"],
    "mouth": ["mulut"],
    "foot": ["kaki"],
    "feet": ["kaki"],
    "head": ["kepala"],
    "voice": ["suara"],
    "face": ["wajah", "muka"],
    "way": ["jalan"],
    "truth": ["kebenaran"],
    "righteousness": ["kebenaran"],
    "judgment": ["penghakiman"],
    "mercy": ["kasih", "rahmat"],
    "grace": ["kasih"],
    "peace": ["damai"],
    "glory": ["kemuliaan"],
    "holy": ["kudus"],
    "blessing": ["berkat"],
    "curse": ["kutuk"],
    "sin": ["dosa"],
    "iniquity": ["kesalahan"],
    "transgression": ["pelanggaran"],
    "enemy": ["musuh"],
    "battle": ["perang"],
    "war": ["perang"],
    "army": ["tentara"],
    "host": ["tentara"],
    "city": ["kota"],
    "gate": ["pintu"],
    "door": ["pintu"],
    "wall": ["tembok"],
    "tower": ["menara"],
    "stone": ["batu"],
    "gold": ["emas"],
    "silver": ["perak"],
    "bronze": ["tembaga"],
    "iron": ["besi"],
    "wood": ["kayu"],
    "tree": ["pohon", "kayu"],
    "wine": ["anggur"],
    "oil": ["minyak"],
    "bread": ["roti"],
    "meat": ["daging"],
    "milk": ["susu"],
    "honey": ["madu"],
    "salt": ["garam"],
    "cloud": ["awan"],
    "wind": ["angin"],
    "rain": ["hujan"],
    "sun": ["matahari"],
    "moon": ["bulan"],
    "star": ["bintang"],
    "stars": ["bintang"],
    "light": ["terang"],
    "darkness": ["gelap"],
    "life": ["hidup"],
    "death": ["maut", "kematian"],
    "seed": ["benih", "keturunan"],
    "fruit": ["buah"],
    "sheep": ["domba"],
    "goat": ["kambing"],
    "ox": ["lembu"],
    "bull": ["sapi"],
    "lamb": ["anak"],
    "cattle": ["ternak"],
    "flock": ["kawanan"],
    "beast": ["binatang"],
    "bird": ["burung"],
    "fish": ["ikan"],
    "man": ["orang"],
    "woman": ["perempuan"],
    "child": ["anak"],
    "children": ["anak"],
    "people": ["bangsa", "orang"],
    "nation": ["bangsa"],
    "multitude": ["banyak"],
    "congregation": ["jemaah"],
    "tribe": ["suku"],
    "family": ["keluarga"],
    "generation": ["keturunan", "angkatan"],
    "beginning": ["mulanya", "permulaan"],
    "end": ["akhir", "kesudahan"],
    "midst": ["tengah"],
    "presence": ["hadirat"],
    "sight": ["pandang"],
    "time": ["masa", "waktu"],
    "year": ["tahun"],
    "month": ["bulan"],
    "week": ["minggu"],
    "morning": ["pagi"],
    "evening": ["petang"],
    "night": ["malam"],
    "noon": ["tengah"],
    "midnight": ["tengah"],
    "age": ["zaman"],
    "everlasting": ["kekal"],
    "eternal": ["kekal"],
    "whole": ["seluruh"],
    "all": ["segala", "semua"],
    "every": ["setiap"],
    "many": ["banyak"],
    "few": ["sedikit"],
    "great": ["besar"],
    "small": ["kecil"],
    "new": ["baru"],
    "old": ["tua", "lama"],
    "first": ["pertama"],
    "last": ["terakhir"],
    "good": ["baik"],
    "evil": ["jahat"],
    "righteous": ["benar"],
    "wicked": ["fasik"],
    "wise": ["bijak"],
    "foolish": ["bodoh"],
    "clean": ["bersih"],
    "unclean": ["najis"],
    "strong": ["kuat"],
    "mighty": ["perkasa", "kuat"],
    "weak": ["lemah"],
    "rich": ["kaya"],
    "poor": ["miskin"],
    "whole": ["seluruh"],
    "deep": ["dalam"],
    "high": ["tinggi"],
    "low": ["rendah"],
    "wonderful": ["ajaib"],
    "glorious": ["mulia"],
    "terrible": ["dahsyat"],
    "sure": ["tetap"],
    "faithful": ["setia"],
    "true": ["benar"],
    "vain": ["sia-sia"],
    "empty": ["kosong"],

    # Verbs
    "said": ["berfirman", "berkata", "kata"],
    "say": ["berkata", "kata"],
    "speak": ["berbicara", "berkata"],
    "spake": ["berfirman", "berkata"],
    "hear": ["dengar"],
    "hearken": ["dengar"],
    "listen": ["dengar"],
    "see": ["lihat"],
    "saw": ["lihat"],
    "look": ["lihat"],
    "behold": ["lihat", "sesungguhnya"],
    "know": ["tahu", "kenal"],
    "knew": ["tahu", "kenal"],
    "make": ["membuat", "menjadikan"],
    "made": ["membuat", "menjadikan"],
    "create": ["menciptakan"],
    "created": ["menciptakan"],
    "give": ["memberi"],
    "gave": ["memberi"],
    "take": ["mengambil"],
    "took": ["mengambil"],
    "bring": ["membawa"],
    "brought": ["membawa"],
    "send": ["mengutus"],
    "sent": ["mengutus"],
    "come": ["datang"],
    "came": ["datang"],
    "go": ["pergi"],
    "went": ["pergi"],
    "stand": ["berdiri"],
    "stood": ["berdiri"],
    "sit": ["duduk"],
    "sat": ["duduk"],
    "walk": ["berjalan"],
    "walked": ["berjalan"],
    "eat": ["makan"],
    "ate": ["makan"],
    "drink": ["minum"],
    "drank": ["minum"],
    "sleep": ["tidur"],
    "slept": ["tidur"],
    "rise": ["bangkit"],
    "rose": ["bangkit"],
    "arise": ["bangun", "bangkit"],
    "arose": ["bangun", "bangkit"],
    "build": ["membangun"],
    "built": ["membangun"],
    "break": ["memecahkan", "mematahkan"],
    "brake": ["memecahkan"],
    "open": ["membuka"],
    "opened": ["membuka"],
    "shut": ["menutup"],
    "close": ["menutup"],
    "remember": ["ingat"],
    "forget": ["lupa"],
    "forgot": ["lupa"],
    "teach": ["mengajar"],
    "taught": ["mengajar"],
    "write": ["menulis"],
    "wrote": ["menulis"],
    "read": ["membaca"],
    "sing": ["bernyanyi"],
    "sang": ["bernyanyi"],
    "rejoice": ["bersukacita"],
    "weep": ["menangis"],
    "wept": ["menangis"],
    "laugh": ["tertawa"],
    "love": ["mengasihi", "kasih"],
    "loved": ["mengasihi"],
    "hate": ["membenci"],
    "hated": ["membenci"],
    "bless": ["memberkati"],
    "blessed": ["memberkati"],
    "curse": ["mengutuk"],
    "cursed": ["mengutuk"],
    "save": ["menyelamatkan"],
    "saved": ["menyelamatkan"],
    "redeem": ["menebus"],
    "redeemed": ["menebus"],
    "forgive": ["mengampuni"],
    "forgave": ["mengampuni"],
    "judge": ["menghakimi"],
    "judged": ["menghakimi"],
    "destroy": ["membinasakan"],
    "destroyed": ["membinasakan"],
    "deliver": ["melepaskan"],
    "delivered": ["melepaskan"],
    "gather": ["mengumpulkan"],
    "gathered": ["mengumpulkan"],
    "scatter": ["menceraiberaikan"],
    "scattered": ["menceraiberaikan"],
    "dwell": ["diam"],
    "dwelt": ["diam"],
    "abide": ["tinggal"],
    "abode": ["tinggal"],
    "command": ["memerintahkan"],
    "commanded": ["memerintahkan"],
    "appoint": ["menetapkan"],
    "appointed": ["menetapkan"],
    "choose": ["memilih"],
    "chose": ["memilih"],
    "chosen": ["pilihan"],
    "anoint": ["mengurapi"],
    "anointed": ["mengurapi"],
    "sanctify": ["menguduskan"],
    "sanctified": ["menguduskan"],
    "consecrate": ["menguduskan"],
    "wash": ["membasuh"],
    "washed": ["membasuh"],
    "worship": ["menyembah"],
    "worshipped": ["menyembah"],
    "serve": ["melayani", "beribadah"],
    "served": ["melayani"],
    "fear": ["takut"],
    "feared": ["takut"],
    "trust": ["percaya"],
    "trusted": ["percaya"],
    "hope": ["berharap"],
    "seek": ["mencari"],
    "sought": ["mencari"],
    "find": ["mendapat"],
    "found": ["mendapat"],
    "keep": ["memelihara", "menjaga"],
    "kept": ["memelihara"],
    "do": ["melakukan"],
    "did": ["melakukan"],
    "done": ["dilakukan"],
    "work": ["pekerjaan"],
    "wrought": ["melakukan"],
    "set": ["menetapkan"],
    "put": ["menaruh"],
    "lay": ["menaruh"],
    "laid": ["menaruh"],
    "lift": ["mengangkat"],
    "lifted": ["mengangkat"],
    "raise": ["membangkitkan"],
    "raised": ["membangkitkan"],
    "bear": ["menanggung"],
    "bare": ["menanggung"],
    "born": ["dilahirkan"],
    "live": ["hidup"],
    "lived": ["hidup"],
    "die": ["mati"],
    "died": ["mati"],
    "bury": ["mengubur"],
    "buried": ["mengubur"],
    "burn": ["membakar"],
    "burnt": ["membakar"],
    "slay": ["membunuh"],
    "slew": ["membunuh"],
    "slain": ["dibunuh"],
    "kill": ["membunuh"],
    "killed": ["membunuh"],
    "smite": ["memukul"],
    "smote": ["memukul"],
    "smiteth": ["memukul"],
    "strike": ["memukul"],
    "struck": ["memukul"],
    "fought": ["berperang"],
    "fight": ["berperang"],
    "conquer": ["menaklukkan"],
    "possess": ["memiliki"],
    "inherit": ["mewarisi"],
    "divide": ["membagi"],
    "numbered": ["dihitung"],
    "count": ["menghitung"],
    "measure": ["mengukur"],
    "weigh": ["menimbang"],
    "buy": ["membeli"],
    "bought": ["membeli"],
    "sell": ["menjual"],
    "sold": ["menjual"],
    "call": ["memanggil", "menamai"],
    "called": ["memanggil", "menamai"],
    "cry": ["berseru"],
    "cried": ["berseru"],
    "answer": ["menjawab"],
    "answered": ["menjawab"],
    "pray": ["berdoa"],
    "prayed": ["berdoa"],
    "beseech": ["memohon"],
    "entreat": ["memohon"],
    "bless": ["memberkati"],

    # Proper names (with TB equivalents)
    "israel": ["israel"],
    "egypt": ["mesir"],
    "babylon": ["babel"],
    "jerusalem": ["yerusalem"],
    "moses": ["musa"],
    "aaron": ["harun"],
    "david": ["daud"],
    "solomon": ["salomo"],
    "samuel": ["samuel"],
    "elijah": ["elia"],
    "elisha": ["elisa"],
    "isaiah": ["yesaya"],
    "jeremiah": ["yeremia"],
    "ezekiel": ["yehezkiel"],
    "daniel": ["daniel"],
    "abraham": ["abraham"],
    "isaac": ["ishak"],
    "jacob": ["yakub"],
    "joseph": ["yusuf"],
    "joshua": ["yosua"],
    "caleb": ["kaleb"],
    "gideon": ["gideon"],
    "samson": ["simson"],
    "ruth": ["rut"],
    "esther": ["ester"],
    "job": ["ayub"],
    "jonah": ["yunus"],
    "noah": ["nuh"],
    "adam": ["adam"],
    "eve": ["hawa"],
    "canaan": ["kanaan"],
    "jordan": ["yordan"],
    "sinai": ["sinai"],
    "eden": ["eden"],
    "zion": ["sion"],
    "pharaoh": ["firaun"],
    "amorite": ["amori"],
    "hittite": ["het"],
    "jebusite": ["yebus"],
    "perizzite": ["perez"],
    "hivite": ["hivi"],
    "girgashite": ["gergasi"],
    "hebrew": ["ibrani"],
    "assyria": ["asyur"],
    "syria": ["aram"],
    "damascus": ["damsyik"],
    "samaria": ["samaria"],
    "galilee": ["galilea"],
    "carmel": ["karmel"],
    "gilgal": ["gilgal"],
    "bethel": ["betel"],
    "shechem": ["sikhem"],
    "hebron": ["hebron"],
    "jericho": ["yerikho"],
    "gibeon": ["gibeon"],
    "shiloh": ["silo"],
    "mizpah": ["mizpa"],
    "ramah": ["rama"],
    "bethlehem": ["betlehem"],
    "nazareth": ["nazaret"],
    "judah": ["yehuda"],
    "benjamin": ["benyamin"],
    "levi": ["levi"],
    "ephraim": ["efraim"],
    "manasseh": ["manasye"],
    "gad": ["gad"],
    "asher": ["asyer"],
    "naphtali": ["naftali"],
    "zebulun": ["zebulon"],
    "issachar": ["iskhar"],
    "dan": ["dan"],
    "simeon": ["simeon"],
    "reuben": ["ruben"],
    "levites": ["levi"],
    "philistines": ["filistin"],
    "moab": ["moab"],
    "ammon": ["amon"],
    "edom": ["edom"],
    "midian": ["midian"],
    "amalek": ["amalek"],

    # Numbers (for verses that have numeric words)
    "one": ["satu", "esa"],
    "two": ["dua"],
    "three": ["tiga"],
    "four": ["empat"],
    "five": ["lima"],
    "six": ["enam"],
    "seven": ["tujuh"],
    "eight": ["delapan"],
    "nine": ["sembilan"],
    "ten": ["sepuluh"],
    "twenty": ["dua"],
    "thirty": ["tiga"],
    "forty": ["empat"],
    "fifty": ["lima"],
    "sixty": ["enam"],
    "seventy": ["tujuh"],
    "eighty": ["delapan"],
    "ninety": ["sembilan"],
    "hundred": ["ratus"],
    "thousand": ["ribu"],
    "first": ["pertama"],
    "second": ["kedua"],
    "third": ["ketiga"],

    # Special divine name phrases
    "am": ["aku"],
    "is": ["adalah"],
    "art": ["adalah"],

    # Additional important missing words
    "born": ["lahir", "dilahirkan"],
    "given": ["diberikan", "beri"],
    "put": ["menaruh"],
    "set": ["menetapkan"],
    "these": ["demikianlah", "inilah"],
    "generations": ["riwayat", "keturunan"],
    "when": ["ketika", "waktu"],
    "prince": ["raja", "pemimpin"],
    "counsellor": ["penasihat", "penasehat"],
    "everlasting": ["kekal"],
    "mighty": ["perkasa"],

    # OT book order / special
    "ark": ["tabut"],
    "tent": ["kemah"],
    "tabernacle": ["kemah"],
    "mercy": ["kasih"],
    "cherub": ["kerub"],
    "cherubims": ["kerub"],
    "lamp": ["pelita"],
    "candlestick": ["kandil"],
    "table": ["meja"],
    "incense": ["ukupan"],
    "laver": ["bejana"],
    "curtain": ["tirai"],
    "veil": ["tabir"],
    "ephod": ["efod"],
    "breastplate": ["tutup"],
    "manna": ["manna"],
    "quail": ["puyuh"],
    "rock": ["batu"],
    "wilderness": ["padang", "gurun"],
    "desert": ["padang"],
    "valley": ["lembah"],
    "hill": ["bukit"],
    "plain": ["dataran"],
    "river": ["sungai"],
    "brook": ["sungai"],
    "fountain": ["mata"],
    "well": ["sumur"],
    "pit": ["lubang"],
    "cave": ["gua"],
    "field": ["ladang"],
    "vineyard": ["kebun"],
    "garden": ["taman"],
    "olive": ["zaitun"],
    "fig": ["ara"],
    "palm": ["korma"],
    "cedar": ["aras"],
    "oak": ["tarbantin"],
    "acacia": ["penaga"],
    "hyssop": ["hisop"],
    "myrrh": ["mur"],
    "frankincense": ["kemenyan"],
    "cinnamon": ["kayu"],
    "cassia": ["kasia"],
    "calamus": ["tebu"],
    "saffron": ["safron"],
    "aloes": ["gaharu"],
    "balm": ["balsam"],
    "syrian": ["aram"],
    "chaldean": ["kasdim"],
}

# Stop words for Indonesian
ID_STOPS = {
    "dan","di","ke","dari","pada","yang","itu","ini","dengan","oleh",
    "untuk","dalam","akan","telah","sudah","adalah","ialah","atau",
    "tetapi","namun","karena","sehingga","maka","pun","lah","kah",
    "kan","ku","mu","nya","si","sang","para","se","ter","per","ber",
    "me","pe","serta","tiada","bukan","ya","hai",
    "satu","seorang","sebuah","beberapa","setiap","masing","sendiri",
    "sama","ada","yakni","bahwa","jika","kalau","sungguh",
    "mari","biarlah","hendaklah","baik","supaya",
    "sementara","selagi","setelah","sebelum",
    "sampai","hingga","antara","juga","lagi","pula",
    "saja","cuma","hanya","sekali","selalu","seluruh","segala",
    "demikian","begitu","begini","suatu","sesuatu",
    "apapun","siapapun","semua",
    "itulah","yakni",
    "kepada","bagi",
    "berfirmanlah",
}


def extract_kjv_tags(text):
    """Extract (word_phrase, strong) pairs from KJV tagged text.
    Handles consecutive tags like [H1254][H853] with empty phrases."""
    pairs = []
    # Split on tags: "text[H123]more[H456]" → ["text", "H123", "more", "H456", ...]
    parts = re.split(r'\[(H\d+)\]', text)
    # parts[0] = text before first tag
    # parts[1] = first tag number (e.g. H7225)
    # parts[2] = text between first and second tag
    # parts[3] = second tag number
    # etc.
    i = 1
    while i < len(parts):
        tag = parts[i]
        phrase_before = parts[i - 1].strip()
        # Clean HTML artifacts from the phrase
        phrase_before = re.sub(r'<[^>]+>', '', phrase_before)
        phrase_before = phrase_before.strip()
        pairs.append((phrase_before, tag))
        i += 2
    return pairs


def parse_kjv_word(word):
    """Extract the last content word from a KJV phrase segment."""
    word = re.sub(r'<[^>]+>', '', word)
    word = word.strip().strip('.,;:!?-\'"()[]""')
    tokens = word.split()
    en_stops = {'the','a','an','of','in','on','at','to','for','with','by',
                'from','and','or',
                'that','this','these','those','which','who','whom',
                'he','him','his','she','her','it','its','they','them',
                'their','we','us','our','you','your','i','me','my',
                'do','did','does','have','has','had','not','no','nor',
                'but','all','when','as','unto','upon'}
    for t in reversed(tokens):
        cleaned = t.strip('.,;:!?-\'"()[]""')
        if cleaned.lower() not in en_stops:
            return cleaned.lower()
    return ''


def tokenize_id(text):
    """Return list of (original, lower, idx) for TB text."""
    result = []
    for i, w in enumerate(text.split()):
        wc = w.strip('.,;:!?-\'"()[]""').lower()
        result.append((w, wc, i))
    return result


def id_lemma(word):
    """Indonesian root form approximation by stripping common affixes."""
    w = word.lower().strip('.,;:!?-\'"()[]""')
    # strip particles
    for p in ['lah', 'kah', 'pun', 'tah']:
        if w.endswith(p) and len(w) > len(p) + 2:
            w = w[:-len(p)]
    # strip possessive
    for p in ['ku', 'mu', 'nya']:
        if w.endswith(p) and len(w) > len(p) + 2:
            w = w[:-len(p)]
    # strip {-kan, -i, -an} suffixes
    for p in ['kan', 'i', 'an']:
        if w.endswith(p) and len(w) > len(p) + 2:
            w2 = w[:-len(p)]
            # Only strip if the result is a reasonable root
            if len(w2) >= 3:
                w = w2
    # strip di- prefix
    if w.startswith('di') and len(w) > 4:
        w = w[2:]
    # strip meN- prefixes
    for p in ['meng', 'meny', 'mem', 'men', 'me']:
        if w.startswith(p) and len(w) > len(p) + 1:
            w2 = w[len(p):]
            # handle nasal assimilation
            if p == 'meng' and w2.startswith('k'):
                w2 = w2[1:]
            elif p == 'meny' and w2.startswith('s'):
                w2 = w2[1:]
            elif p == 'mem' and w2.startswith('p'):
                w2 = w2[1:]
            elif p == 'men' and w2.startswith('t'):
                w2 = w2[1:]
            if len(w2) >= 3:
                w = w2
                break
    # strip per- / peN- prefixes
    for p in ['peng', 'peny', 'pem', 'pen', 'per', 'pe']:
        if w.startswith(p) and len(w) > len(p) + 1:
            w2 = w[len(p):]
            if p == 'peng' and w2.startswith('k'):
                w2 = w2[1:]
            elif p == 'peny' and w2.startswith('s'):
                w2 = w2[1:]
            elif p == 'pem' and w2.startswith('p'):
                w2 = w2[1:]
            elif p == 'pen' and w2.startswith('t'):
                w2 = w2[1:]
            if len(w2) >= 3:
                w = w2
                break
    # strip ke- / se- prefix
    for p in ['ke', 'se']:
        if w.startswith(p) and len(w) > len(p) + 2:
            w = w[len(p):]
    # strip ber- prefix
    if w.startswith('ber') and len(w) > 4:
        w2 = w[3:]
        if len(w2) >= 3:
            w = w2
    # strip ter- prefix
    if w.startswith('ter') and len(w) > 4:
        w2 = w[3:]
        if len(w2) >= 3:
            w = w2
    return w


def tag_verse(tb_text, kjv_text):
    """Align KJV Strong's tags to TB words using bilingual dictionary + position."""
    pairs = extract_kjv_tags(kjv_text)
    if not pairs:
        return tb_text

    tokens = tokenize_id(tb_text)
    tb_words = [t[0] for t in tokens]
    tb_lower = [t[1] for t in tokens]
    n_tb = len(tb_words)

    # Get unique Strong's numbers in order of first appearance
    seen = set()
    strongs_order = []
    for _, s in pairs:
        if s not in seen:
            seen.add(s)
            strongs_order.append(s)

    # Build ordered list of (en_word, strong) from KJV pairs
    kjv_entries = []
    for phrase, s in pairs:
        en = parse_kjv_word(phrase)
        if en:
            kjv_entries.append((en, s))
        else:
            kjv_entries.append(("", s))

    assigned = {}
    assigned_positions = set()
    # Count how many times each Strong's appears in the KJV
    strong_count = defaultdict(int)
    for _, s in kjv_entries:
        strong_count[s] += 1
    assigned_count = defaultdict(int)

    def done(strong):
        return assigned_count[strong] >= strong_count[strong]

    # Pre-compute lemmas for each TB word
    tb_lemmas = {}
    for i, (orig, wc, idx) in enumerate(tokens):
        tb_lemmas[i] = id_lemma(orig)

    # ── Phase 1: Dictionary-based alignment ──
    for kjv_idx, (en_word, strong) in enumerate(kjv_entries):
        if not en_word:
            continue
        if done(strong):
            continue

        candidates = []

        # Try dictionary matching (original + lemma)
        if en_word in BILINGUAL:
            for id_word in BILINGUAL[en_word]:
                id_lemma_form = id_lemma(id_word)
                for i, (orig, wc, idx) in enumerate(tokens):
                    if i in assigned_positions:
                        continue
                    if wc == id_word or tb_lemmas[i] == id_word or tb_lemmas[i] == id_lemma_form:
                        pos_score = 1.0 - abs(i - kjv_idx) / max(1, n_tb)
                        candidates.append((i, 2.0 + pos_score))

        # Exact match of English word in TB
        if not candidates:
            for i, (orig, wc, idx) in enumerate(tokens):
                if i in assigned_positions:
                    continue
                if wc == en_word:
                    pos_score = 1.0 - abs(i - kjv_idx) / max(1, n_tb)
                    candidates.append((i, 1.0 + pos_score))

        # Lemma-root matching
        if not candidates and en_word:
            en_root = en_word.rstrip('ed')
            if len(en_root) >= 4:
                for i, (orig, wc, idx) in enumerate(tokens):
                    if i in assigned_positions:
                        continue
                    if en_root in tb_lemmas[i] or tb_lemmas[i] in en_root:
                        pos_score = 1.0 - abs(i - kjv_idx) / max(1, n_tb)
                        candidates.append((i, 0.8 + pos_score))

        if candidates:
            candidates.sort(key=lambda x: (-x[1], abs(x[0] - kjv_idx)))
            best_pos = candidates[0][0]
            assigned[best_pos] = strong
            assigned_positions.add(best_pos)
            assigned_count[strong] += 1

    # ── Phase 2: Positional alignment for remaining ──
    unassigned_positions = [i for i in range(n_tb) if i not in assigned_positions]

    # Build list of remaining (kjv_idx, strong) for entries not yet assigned
    remaining_entries = [(i, en, s) for i, (en, s) in enumerate(kjv_entries)
                         if en and not done(s)]

    if remaining_entries and unassigned_positions:
        for kjv_idx, en_word, strong in remaining_entries:
            if done(strong):
                continue
            # Scale to TB position
            scaled_pos = kjv_idx * n_tb / max(1, len(kjv_entries))
            target_tb_idx = round(scaled_pos)
            if not unassigned_positions:
                break
            nearest = min(unassigned_positions, key=lambda p: abs(p - target_tb_idx))
            if abs(nearest - target_tb_idx) <= max(4, n_tb // 2):
                assigned[nearest] = strong
                assigned_positions.add(nearest)
                assigned_count[strong] += 1
                unassigned_positions.remove(nearest)

    # ── Phase 3: Stragglers → remaining content word positions ──
    still_free = [i for i in range(n_tb) if i not in assigned_positions]
    still_pending = [s for s in strong_count if not done(s)]

    content_free = [i for i in still_free
                    if tb_lower[i] not in ID_STOPS
                    and any(c.isalpha() for c in tb_lower[i])]

    n = len(still_pending)
    m = len(content_free)
    if n > 0 and m > 0:
        for j, s in enumerate(still_pending):
            pos = content_free[min(j, m - 1)]
            assigned[pos] = s
            assigned_count[s] += 1

    # ── Apply tags ──
    result = list(tb_words)
    for idx in sorted(assigned, reverse=True):
        if idx < len(result):
            result[idx] = f"{result[idx]}[{assigned[idx]}]"

    return ' '.join(result)


def main():
    conn = sqlite3.connect(DB_PATH)

    # Clean existing tag remnants
    print("Cleaning Strong's tag remnants...", file=sys.stderr)
    rows = conn.execute('SELECT rowid, text FROM strong_id').fetchall()
    cleaned = 0
    for rowid, text in rows:
        new_text = re.sub(r'\[?H\d+\]?', '', text)
        new_text = re.sub(r'  +', ' ', new_text).strip()
        if new_text != text:
            conn.execute('UPDATE strong_id SET text=? WHERE rowid=?', (new_text, rowid))
            cleaned += 1
    conn.commit()
    print(f"  Cleaned {cleaned} verses", file=sys.stderr)
    print(f"  Loaded {len(BILINGUAL)} bilingual dictionary entries", file=sys.stderr)

    print("Tagging TB OT verses...", file=sys.stderr)

    rows = conn.execute(
        "SELECT s.book_code, s.chapter, s.verse, s.text, i.text "
        "FROM strong_en s JOIN strong_id i "
        "ON s.book_code=i.book_code AND s.chapter=i.chapter AND s.verse=i.verse "
        "WHERE s.book_code IN ({}) "
        "ORDER BY s.book_code, s.chapter, s.verse".format(
            ','.join('?' for _ in OT_BOOKS)
        ), OT_BOOKS
    ).fetchall()

    updated = 0
    for bk, ch, vs, kjv_text, tb_text in rows:
        tagged = tag_verse(tb_text, kjv_text)
        if tagged != tb_text:
            conn.execute(
                "UPDATE strong_id SET text=? WHERE book_code=? AND chapter=? AND verse=?",
                (tagged, bk, ch, vs)
            )
            updated += 1

        if updated % 500 == 0:
            conn.commit()
            print(f"  Progress: {updated} tagged", file=sys.stderr)

    conn.commit()
    conn.close()
    print(f"\nDone. Tagged {updated} verses", file=sys.stderr)


if __name__ == "__main__":
    main()
