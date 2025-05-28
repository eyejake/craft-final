from flask import Flask, request, jsonify, send_from_directory
import random
import string
import requests
from datetime import datetime, timedelta

app = Flask(__name__, static_folder=".")

users = {}
LETTER_POOL_SIZE = 7
VOWELS = ['A', 'E', 'I', 'O', 'U']

LETTER_POINTS = {
    'A': 1, 'B': 3, 'C': 3, 'D': 2, 'E': 1, 'F': 4, 'G': 2, 'H': 4,
    'I': 1, 'J': 8, 'K': 5, 'L': 1, 'M': 3, 'N': 1, 'O': 1, 'P': 3,
    'Q': 10, 'R': 1, 'S': 1, 'T': 1, 'U': 1, 'V': 4, 'W': 4, 'X': 8,
    'Y': 4, 'Z': 10
}

SCRABBLE_LETTER_POOL = (
    ['E'] * 12 + ['A'] * 9 + ['I'] * 9 + ['O'] * 8 + ['N'] * 6 + ['R'] * 6 + ['T'] * 6 + ['L'] * 4 + ['S'] * 4 + ['U'] * 4 +
    ['D'] * 4 + ['G'] * 3 + ['B'] * 2 + ['C'] * 2 + ['M'] * 2 + ['P'] * 2 +
    ['F'] * 2 + ['H'] * 2 + ['V'] * 2 + ['W'] * 2 + ['Y'] * 2 + ['K'] * 1 + ['J'] * 1 + ['X'] * 1 + ['Q'] * 1 + ['Z'] * 1
)


def get_seeded_letters(date_seed, n=LETTER_POOL_SIZE):
    random.seed(date_seed)
    letters = []
    for _ in range(2):
        letters.append(random.choice(VOWELS))
    while len(letters) < n:
        letters.append(random.choice(SCRABBLE_LETTER_POOL))
    random.shuffle(letters)
    return letters


def is_valid_word(word):
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{word.lower()}"
    response = requests.get(url)
    return response.status_code == 200


def calculate_word_score(word):
    return sum(LETTER_POINTS.get(letter.upper(), 0) for letter in word)


@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')


@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    today_key = datetime.utcnow().strftime('%Y-%m-%d')
    if username not in users:
        users[username] = {
            'letters': get_seeded_letters(today_key),
            'history': [],
            'dictionary': [],  # store unique submitted words with scores
            'date': today_key,
            'last_submission': None,
            'tokens': 10,
            'score': 0,
            'highest_score': 0,
            'best_word': '',
            'longest_word': '',
            'current_streak': 0,
            'longest_streak': 0,
            'last_login': None,
            'login_days': set(),
            'achievements': []
        }
    user = users[username]
    if 'best_word' not in user:
        user['best_word'] = max(user.get('history', []), key=lambda w: calculate_word_score(w), default='')
    if 'longest_word' not in user:
        user['longest_word'] = max(user.get('history', []), key=len, default='')
    if user['date'] != today_key:
        user['letters'] = get_seeded_letters(today_key)
        user['date'] = today_key

    today = datetime.utcnow().date()
    if user['last_login']:
        last_login = datetime.strptime(user['last_login'], '%Y-%m-%d').date()
        if today - last_login == timedelta(days=1):
            user['current_streak'] += 1
        elif today - last_login > timedelta(days=1):
            user['current_streak'] = 1
    else:
        user['current_streak'] = 1

    user['longest_streak'] = max(user['longest_streak'], user['current_streak'])
    user['last_login'] = today.strftime('%Y-%m-%d')
    user['login_days'].add(today_key)

    new_achievements = []
    if user['current_streak'] >= 3 and "Logged in 3 days in a row" not in user['achievements']:
        user['achievements'].append("Logged in 3 days in a row")
        new_achievements.append("Logged in 3 days in a row")

    return jsonify({
        "status": "success",
        "username": username,
        "achievements": user['achievements'],
        "new_achievements": new_achievements
    })


@app.route('/get-letters', methods=['GET'])
def get_letters():
    username = request.args.get('username')
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    today_key = datetime.utcnow().strftime('%Y-%m-%d')
    submitted_today = user.get('last_submission') == today_key
    last_word = user['history'][-1] if submitted_today and user['history'] else ''
    last_score = calculate_word_score(last_word) if last_word else 0

    return jsonify({
        "letters": user['letters'],
        "tokens": user['tokens'],
        "score": user['score'],
        "highest_score": user['highest_score'],
        "best_word": user.get('best_word') or max(user['history'], key=lambda w: calculate_word_score(w), default=""),
        "longest_word": user.get('longest_word') or max(user['history'], key=len, default=""),
        "current_streak": user['current_streak'],
        "longest_streak": user['longest_streak'],
        "achievements": user['achievements'],
        "dictionary": user['dictionary'],
        "dictionary_score": sum(entry['score'] for entry in user['dictionary']),
        "submitted_today": submitted_today,
        "last_word": last_word,
        "last_word_score": last_score
    })


@app.route('/submit-word', methods=['POST'])
def submit_word():
    data = request.json
    username = data['username']
    word = data['word'].upper()
    today_key = datetime.utcnow().strftime('%Y-%m-%d')

    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if user.get('last_submission') == today_key:
        return jsonify({"status": "fail", "message": "You've already submitted a word today."})

    new_achievements = []
    first_word = len(user['history']) == 0

    letters_copy = user['letters'][:]
    for char in word:
        if char in letters_copy:
            letters_copy.remove(char)
        else:
            return jsonify({"status": "fail", "message": "Invalid use of letters"})

    if not is_valid_word(word):
        return jsonify({"status": "fail", "message": "Not a valid dictionary word"})

    score = calculate_word_score(word)
    user['history'].append(word)
    if not any(entry['word'] == word for entry in user['dictionary']):
        user['dictionary'].append({"word": word, "score": score})
    user['last_submission'] = today_key
    user['tokens'] += 1
    if len(word) == LETTER_POOL_SIZE:
        user['tokens'] += 3

    user['score'] += score
    if score > user['highest_score']:
        user['highest_score'] = score
        user['best_word'] = word
    if len(word) > len(user['longest_word']):
        user['longest_word'] = word

    if first_word and "First word submitted" not in user['achievements']:
        user['achievements'].append("First word submitted")
        new_achievements.append("First word submitted")
    if score >= 10 and "Scored 10+ points in a word" not in user['achievements']:
        user['achievements'].append("Scored 10+ points in a word")
        new_achievements.append("Scored 10+ points in a word")
    if len(word) == LETTER_POOL_SIZE and "Used all 7 letters" not in user['achievements']:
        user['achievements'].append("Used all 7 letters")
        new_achievements.append("Used all 7 letters")

    if len(word) == len(user['letters']):
        user['letters'] = get_seeded_letters(today_key)
    else:
        user['letters'] = letters_copy

    result = {
        "status": "success",
        "new_letters": user['letters'],
        "word": word,
        "score": score,
        "total_score": user['score'],
        "tokens": user['tokens'],
        "highest_score": user['highest_score'],
        "best_word": user['best_word'],
        "longest_word": user['longest_word'],
        "achievements": user['achievements'],
        "new_achievements": new_achievements,
        "dictionary": user['dictionary'],
        "dictionary_score": sum(entry['score'] for entry in user['dictionary'])
    }
    print("Response Payload:", result)
    return jsonify(result)


@app.route('/fast-forward-day', methods=['POST'])
def fast_forward_day():
    username = request.json.get('username')
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    current_date = datetime.strptime(user['date'], '%Y-%m-%d').date()
    next_day = current_date + timedelta(days=1)
    next_key = next_day.strftime('%Y-%m-%d')

    user['letters'] = get_seeded_letters(next_key)
    user['date'] = next_key
    user['last_submission'] = None

    if user['last_login']:
        last_login = datetime.strptime(user['last_login'], '%Y-%m-%d').date()
        if next_day - last_login == timedelta(days=1):
            user['current_streak'] += 1
        elif next_day - last_login > timedelta(days=1):
            user['current_streak'] = 1
    else:
        user['current_streak'] = 1

    user['longest_streak'] = max(user['longest_streak'], user['current_streak'])
    user['last_login'] = next_key
    user['login_days'].add(next_key)

    new_achievements = []
    if user['current_streak'] >= 3 and "Logged in 3 days in a row" not in user['achievements']:
        user['achievements'].append("Logged in 3 days in a row")
        new_achievements.append("Logged in 3 days in a row")

    return jsonify({
        "status": "success",
        "letters": user['letters'],
        "date": next_key,
        "new_achievements": new_achievements
    })


if __name__ == '__main__':
    app.run(debug=True)
