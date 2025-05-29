from flask import Flask, request, jsonify, send_from_directory
import random
import string
import requests
from datetime import datetime, timedelta

app = Flask(__name__, static_folder=".")

users = {}
LETTER_POOL_SIZE = 7
ACHIEVEMENT_TOKEN_REWARD = 2
MAX_TILES = 10
VOWELS = ['A', 'E', 'I', 'O', 'U']
MILESTONES = [3, 7, 21]

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

def get_random_letters(n=LETTER_POOL_SIZE):
    """Return a random set of letters independent of the daily seed."""
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

def grant_milestone_reward(user):
    streak = user['current_streak']
    reward = {"milestone": streak}
    if streak == 3:
        tiles = [random.choice(SCRABBLE_LETTER_POOL)]
        user['letters'].extend(tiles)
        reward["tiles"] = tiles
    elif streak == 7:
        tiles = [random.choice(SCRABBLE_LETTER_POOL) for _ in range(2)]
        user['letters'].extend(tiles)
        reward["tiles"] = tiles
    elif streak == 21:
        tiles = [random.choice(SCRABBLE_LETTER_POOL) for _ in range(3)]
        user['letters'].extend(tiles)
        user['tokens'] += 10
        reward["tiles"] = tiles
        reward["tokens"] = 10
    return reward

def apply_daily_login(user, date_key):
    # Apply daily login logic for the given date
    if user['date'] != date_key:
        if user.get('last_login') is None:
            user['letters'] = get_random_letters()
        else:
            if len(user['letters']) == 0:
                user['letters'] = get_random_letters()
            elif len(user['letters']) < MAX_TILES:
                user['letters'].append(random.choice(SCRABBLE_LETTER_POOL))
        user['date'] = date_key
        user['last_submission'] = None
        user['submissions_today'] = 0

    today = datetime.strptime(date_key, '%Y-%m-%d').date()
    if user['last_login']:
        last_login = datetime.strptime(user['last_login'], '%Y-%m-%d').date()
        if today - last_login == timedelta(days=1):
            user['current_streak'] += 1
        elif today - last_login > timedelta(days=1):
            user['current_streak'] = 1
    else:
        user['current_streak'] = 1

    user['longest_streak'] = max(user['longest_streak'], user['current_streak'])
    user['last_login'] = date_key
    user['login_days'].add(date_key)

    new_achievements = []
    tokens_earned = 0
    if user['current_streak'] >= 3 and "Logged in 3 days in a row" not in user['achievements']:
        user['achievements'].append("Logged in 3 days in a row")
        new_achievements.append("Logged in 3 days in a row")
        tokens_earned += ACHIEVEMENT_TOKEN_REWARD

    if user['current_streak'] >= 3:
        if user['current_streak'] % 3 == 0 and user.get('last_spin_streak', 0) != user['current_streak']:
            user['spin_available'] = True
    else:
        user['spin_available'] = False

    reward = None
    if user['current_streak'] in MILESTONES:
        reward = grant_milestone_reward(user)

    return new_achievements, tokens_earned, reward

def check_achievements(user, word=None, score=None, event_type=None):
    """Check and award achievements based on the event type."""
    new_achievements = []
    tokens = 0

    if event_type == 'login':
        if user['current_streak'] >= 3 and "Logged in 3 days in a row" not in user['achievements']:
            user['achievements'].append("Logged in 3 days in a row")
            new_achievements.append("Logged in 3 days in a row")
            tokens += ACHIEVEMENT_TOKEN_REWARD

    if event_type == 'submission':
        if len(user['history']) == 1 and "First word submitted" not in user['achievements']:
            user['achievements'].append("First word submitted")
            new_achievements.append("First word submitted")
            tokens += ACHIEVEMENT_TOKEN_REWARD
        if score is not None and score >= 10 and "Scored 10+ points in a word" not in user['achievements']:
            user['achievements'].append("Scored 10+ points in a word")
            new_achievements.append("Scored 10+ points in a word")
            tokens += ACHIEVEMENT_TOKEN_REWARD
        if word is not None and len(word) == LETTER_POOL_SIZE and "Used all 7 letters" not in user['achievements']:
            user['achievements'].append("Used all 7 letters")
            new_achievements.append("Used all 7 letters")
            tokens += ACHIEVEMENT_TOKEN_REWARD

    if event_type == 'wordcount':
        count = len(user['dictionary'])
        if count >= 5 and "Found 5 words" not in user['achievements']:
            user['achievements'].append("Found 5 words")
            new_achievements.append("Found 5 words")
            tokens += ACHIEVEMENT_TOKEN_REWARD
        if count >= 10 and "Found 10 words" not in user['achievements']:
            user['achievements'].append("Found 10 words")
            new_achievements.append("Found 10 words")
            tokens += ACHIEVEMENT_TOKEN_REWARD

    return new_achievements, tokens

@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    today_key = datetime.utcnow().strftime('%Y-%m-%d')
    if username not in users:
        users[username] = {
            'letters': get_random_letters(),
            'history': [],
            'dictionary': [],
            'date': today_key,
            'last_submission': None,
            'submissions_today': 0,
            'tokens': 10,
            'score': 0,
            'highest_score': 0,
            'best_word': '',
            'longest_word': '',
            'current_streak': 0,
            'longest_streak': 0,
            'last_login': None,
            'login_days': set(),
            'achievements': [],
            'spin_available': False,
            'last_spin_streak': 0,
            'tokens_spent': 0,
            'tiles_swapped': 0
        }
    user = users[username]
    if 'best_word' not in user:
        user['best_word'] = max(user.get('history', []), key=lambda w: calculate_word_score(w), default='')
    if 'longest_word' not in user:
        user['longest_word'] = max(user.get('history', []), key=len, default='')

    daily_achievements, earned, milestone_reward = apply_daily_login(user, today_key)
    if earned:
        user['tokens'] += earned

    login_achievements, login_tokens = check_achievements(user, event_type='login')
    if login_tokens:
        user['tokens'] += login_tokens

    all_new = []
    all_new.extend(daily_achievements)
    all_new.extend(login_achievements)

    return jsonify({
        "status": "success",
        "username": username,
        "tokens": user['tokens'],
        "achievements": user['achievements'],
        "milestone_reward": milestone_reward,
        "new_achievements": all_new
    })

@app.route('/get-letters', methods=['GET'])
def get_letters():
    username = request.args.get('username')
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    today_key = datetime.utcnow().strftime('%Y-%m-%d')
    submitted_today = user['date'] == today_key and user['submissions_today'] > 0
    last_word = user['history'][-1] if submitted_today and user['history'] else ''
    last_score = calculate_word_score(last_word) if last_word else 0
    next_milestone = next((m for m in MILESTONES if user['current_streak'] < m), MILESTONES[-1])

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
        "last_word_score": last_score,
        "spin_available": user.get('spin_available', False),
        "submissions_today": user['submissions_today'],
        "next_milestone": next_milestone,
        "next_cost": user['submissions_today']
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

    if user['date'] != today_key:
        daily_achievements, earned, _ = apply_daily_login(user, today_key)
        if earned:
            user['tokens'] += earned
    
    cost = user['submissions_today']
    if user['tokens'] < cost:
        return jsonify({"status": "fail", "message": "Not enough tokens"})

    new_achievements = []
    if user['date'] != today_key:
        new_achievements.extend(daily_achievements if 'daily_achievements' in locals() else [])

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
    user['tokens'] -= cost
    user['tokens_spent'] += cost
    if len(word) == LETTER_POOL_SIZE:
        user['tokens'] += 3

    user['score'] += score
    if score > user['highest_score']:
        user['highest_score'] = score
        user['best_word'] = word
    if len(word) > len(user['longest_word']):
        user['longest_word'] = word

    tokens_from_achievements = 0
    submission_achievements, earned = check_achievements(
        user, word, score, event_type='submission'
    )
    tokens_from_achievements += earned
    new_achievements.extend(submission_achievements)

    vocab_achievements, vocab_tokens = check_achievements(user, event_type='wordcount')
    tokens_from_achievements += vocab_tokens
    new_achievements.extend(vocab_achievements)

    if len(word) == len(user['letters']):
        # Rack is empty after playing this word; refill with random letters
        user['letters'] = get_random_letters()
    else:
        user['letters'] = letters_copy

    user['tokens'] += tokens_from_achievements
    user['submissions_today'] += 1

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

@app.route('/spin', methods=['POST'])
def spin_wheel():
    username = request.json.get('username')
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if not user.get('spin_available'):
        return jsonify({"status": "fail", "message": "Spin not available"})

    available_slots = MAX_TILES - len(user['letters'])
    new_tiles = []
    if available_slots > 0:
        tiles_to_add = min(random.randint(1, 3), available_slots)
        new_tiles = [random.choice(SCRABBLE_LETTER_POOL) for _ in range(tiles_to_add)]
        user['letters'].extend(new_tiles)

    tokens_won = random.randint(1, 3)
    user['tokens'] += tokens_won

    user['spin_available'] = False
    user['last_spin_streak'] = user['current_streak']

    return jsonify({"status": "success", "new_tiles": new_tiles, "tokens": user['tokens'], "tokens_won": tokens_won, "letters": user['letters']})


@app.route('/swap-letters', methods=['POST'])
def swap_letters():
    data = request.json
    username = data.get('username')
    letters = data.get('letters', [])
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    letters_upper = [str(l).upper() for l in letters]
    letters_copy = user['letters'][:]
    indices_to_swap = []
    for l in letters_upper:
        if l in letters_copy:
            idx = letters_copy.index(l)
            indices_to_swap.append(idx)
            letters_copy[idx] = None

    cost = len(indices_to_swap) * 2
    if user['tokens'] < cost:
        return jsonify({"status": "fail", "message": "Not enough tokens"})

    user['tokens'] -= cost
    user['tokens_spent'] += cost
    for idx in indices_to_swap:
        user['letters'][idx] = random.choice(SCRABBLE_LETTER_POOL)
        user['tiles_swapped'] += 1

    return jsonify({"status": "success", "letters": user['letters'], "tokens": user['tokens']})

@app.route('/buy-tiles', methods=['POST'])
def buy_tiles():
    data = request.json
    username = data.get('username')
    count = int(data.get('count', 0))
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    if count <= 0:
        return jsonify({"status": "fail", "message": "Invalid tile count"})

    available_slots = MAX_TILES - len(user['letters'])
    if count > available_slots:
        return jsonify({"status": "fail", "message": "Rack cannot hold that many tiles"})

    cost = count * 2
    if user['tokens'] < cost:
        return jsonify({"status": "fail", "message": "Not enough tokens"})

    user['tokens'] -= cost
    user['tokens_spent'] += cost
    new_tiles = [random.choice(SCRABBLE_LETTER_POOL) for _ in range(count)]
    user['letters'].extend(new_tiles)

    return jsonify({"status": "success", "letters": user['letters'], "tokens": user['tokens'], "new_tiles": new_tiles})

@app.route('/fast-forward-day', methods=['POST'])
def fast_forward_day():
    username = request.json.get('username')
    user = users.get(username)
    if not user:
        return jsonify({"status": "error", "message": "User not found"}), 404

    current_date = datetime.strptime(user['date'], '%Y-%m-%d').date()
    next_day = current_date + timedelta(days=1)
    next_key = next_day.strftime('%Y-%m-%d')

    new_achievements, earned, milestone_reward = apply_daily_login(user, next_key)
    if earned:
        user['tokens'] += earned

    return jsonify({
        "status": "success",
        "letters": user['letters'],
        "date": next_key,
        "new_achievements": new_achievements,
        "spin_available": user.get('spin_available', False),
        "tokens": user['tokens'],
        "milestone_reward": milestone_reward
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000)
