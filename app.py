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
            'date': today_key,
            'last_submission': None,
            'tokens': 10,
            'score': 0,
            'highest_score': 0,
            'longest_word': '',
            'current_streak': 0,
            'longest_streak': 0,
            'last_login': None,
            'login_days': set()
        }
    user = users[username]
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

    return jsonify({"status": "success", "username": username})


@app.route('/get-letters', methods=['GET'])
def get_letters():
    username = request.args.get('username')
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404
    return jsonify({
        "letters": user['letters'],
        "tokens": user['tokens'],
        "score": user['score'],
        "highest_score": user['highest_score'],
        "best_word": max(user['history'], key=lambda w: calculate_word_score(w), default=""),
        "longest_word": user['longest_word'],
        "current_streak": user['current_streak'],
        "longest_streak": user['longest_streak']
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
    user['last_submission'] = today_key
    user['tokens'] += 1
    if len(word) == LETTER_POOL_SIZE:
        user['tokens'] += 3

    user['score'] += score
    if score > user['highest_score']:
        user['highest_score'] = score
    if len(word) > len(user['longest_word']):
        user['longest_word'] = word

    if len(word) == len(user['letters']):
        user['letters'] = get_seeded_letters(today_key)
    else:
        user['letters'] = letters_copy

    result = {
        "status": "success",
        "new_letters": user['letters'],
        "word": word,
        "score": score,
        "tokens": user['tokens']
    }
    print("Response Payload:", result)
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)
