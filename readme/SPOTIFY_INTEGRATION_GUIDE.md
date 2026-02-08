# Spotify Integration Guide for StudyOS

This guide provides detailed, step-by-step instructions to integrate Spotify music playback into the Study Mode page.

## Alternative: Spotify Embed (No API Key Required)

If you cannot access the Spotify Developer Dashboard, you can use the **Spotify Embed** player. This allows users to play a 30-second preview or log in to their Spotify account to listen to full tracks directly in the browser.

### 1. Simple Embed Code

Add this `<iframe>` to your `study_mode.html` where you want the player to appear:

```html
<!-- Spotify Embed Player -->
<div class="spotify-card">
    <h3>Study Music</h3>
    <iframe style="border-radius:12px" src="https://open.spotify.com/embed/playlist/37i9dQZF1DX8Uebhn9wqrS?utm_source=generator&theme=0" width="100%" height="352" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>
</div>
```

*   **Playlist URL**: Replace the `src` URL with any public Spotify playlist URL (e.g., Lofi Hip Hop).
*   **Limitations**: Preview only for non-logged-in users. Full playback requires user login in the embed.

---

## Full Integration (Requires Developer API Key)

Follow these steps once the Spotify Developer Dashboard is back online.

### Prerequisites

1.  **Spotify Developer Account**:
    *   Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
    *   Log in and click **"Create App"**.
    *   **App Name**: `StudyOS`
    *   **Redirect URI**: `http://localhost:5000/callback` (Exact match required)
    *   Save and note down your **Client ID** and **Client Secret**.

### Step 1: Install Dependencies

Open your terminal in the project root (`c:\Users\HP\Downloads\TEST1`) and run:

```bash
pip install spotipy
```

### Step 2: Backend Implementation (`app.py`)

You need to modify `c:\Users\HP\Downloads\TEST1\app.py`.

#### 1. Add Imports
**Location**: Top of the file, around line 15.

```python
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import time
```

#### 2. Add Configuration & Helper
**Location**: After `app.secret_key = os.urandom(24)` (around line 20).

```python
# SPOTIFY CONFIGURATION
SPOTIFY_CLIENT_ID = 'YOUR_CLIENT_ID_HERE'  # Replace with your actual Client ID
SPOTIFY_CLIENT_SECRET = 'YOUR_CLIENT_SECRET_HERE' # Replace with your actual Client Secret
SPOTIFY_REDIRECT_URI = 'http://localhost:5000/callback'
SCOPE = "user-read-playback-state user-modify-playback-state streaming user-read-email user-read-private playlist-read-private"

def get_spotify_oauth():
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=SCOPE
    )
```

#### 3. Add Authentication Routes
**Location**: Before `Study Mode` section (around line 656, before `@app.route('/study-mode')`).

```python
@app.route('/spotify/login')
def spotify_login():
    sp_oauth = get_spotify_oauth()
    auth_url = sp_oauth.get_authorize_url()
    return redirect(auth_url)

@app.route('/callback')
def spotify_callback():
    sp_oauth = get_spotify_oauth()
    code = request.args.get('code')
    token_info = sp_oauth.get_access_token(code)
    session['token_info'] = token_info
    return redirect(url_for('study_mode'))

def get_token():
    token_info = session.get('token_info', None)
    if not token_info:
        return None
    now = int(time.time())
    is_expired = token_info['expires_at'] - now < 60
    if is_expired:
        sp_oauth = get_spotify_oauth()
        token_info = sp_oauth.refresh_access_token(token_info['refresh_token'])
        session['token_info'] = token_info
    return token_info
```

#### 4. Update `study_mode` Route
**Location**: Inside `study_mode()` function (around line 660).

**Original Code**:
```python
@app.route('/study-mode')
@require_login
def study_mode():
    uid = session['uid']
    user_data = get_user_data(uid)
    name = user_data.get('name', 'Student') if user_data else 'Student'
    
    todos = db.collection('users').document(uid)\
        .collection('study_todos').stream()
    todo_list = [{'id': t.id, **t.to_dict()} for t in todos]

    return render_template(
        'study_mode.html',
        name=name,
        todos=todo_list
    )
```

**New Code** (Replace the function content):
```python
@app.route('/study-mode')
@require_login
def study_mode():
    uid = session['uid']
    user_data = get_user_data(uid)
    name = user_data.get('name', 'Student') if user_data else 'Student'
    
    todos = db.collection('users').document(uid)\
        .collection('study_todos').stream()
    todo_list = [{'id': t.id, **t.to_dict()} for t in todos]

    # --- SPOTIFY TOKEN CHECK ---
    token_info = get_token()
    spotify_token = token_info['access_token'] if token_info else None
    # ---------------------------

    return render_template(
        'study_mode.html',
        name=name,
        todos=todo_list,
        spotify_token=spotify_token  # Pass token to template
    )
```

### Step 3: Frontend Implementation (`study_mode.html`)

Modify `c:\Users\HP\Downloads\TEST1\templates\study_mode.html`.

#### 1. Add Spotify Card
**Location**: Add inside `.study-mode-layout`, **after** the `study-timer-card` closing div (around line 60) and **before** `study-todo-card`.

```html
<!-- SPOTIFY CARD (Add between Timer and Todo) -->
<div class="spotify-card">
    <h3 style="margin-bottom:15px; font-size:18px;">Study Music</h3>
    
    {% if not spotify_token %}
        <a href="{{ url_for('spotify_login') }}" class="btn-spotify">
            Connect Spotify
        </a>
    {% else %}
        <div id="player-status" style="margin-bottom:10px; color:var(--text-muted);">Player Ready</div>
        <div class="player-controls">
            <button id="prevBtn">⏮</button>
            <button id="togglePlayBtn">⏯</button>
            <button id="nextBtn">⏭</button>
        </div>
        <div id="current-track" style="margin-top:10px; font-weight:500;">No track playing</div>
    {% endif %}
</div>
```

#### 2. Add SDK Script
**Location**: At the very bottom of the body, **before** the other scripts (around line 90).

```html
<script src="https://sdk.scdn.co/spotify-player.js"></script>
```

#### 3. Add Player Logic
**Location**: Add a **new** `<script>` block at the end of the file (around line 180, before `</body>`).

```html
<script>
    {% if spotify_token %}
    window.onSpotifyWebPlaybackSDKReady = () => {
        const token = '{{ spotify_token }}';
        const player = new Spotify.Player({
            name: 'StudyOS Web Player',
            getOAuthToken: cb => { cb(token); },
            volume: 0.5
        });

        player.addListener('ready', ({ device_id }) => {
            console.log('Ready with Device ID', device_id);
            document.getElementById('player-status').innerText = "Connected";
        });

        player.addListener('player_state_changed', state => {
            if (!state) return;
            document.getElementById('current-track').innerText = 
                state.track_window.current_track.name + " - " + 
                state.track_window.current_track.artists[0].name;
        });

        player.connect();

        document.getElementById('togglePlayBtn').onclick = () => { player.togglePlay(); };
        document.getElementById('prevBtn').onclick = () => { player.previousTrack(); };
        document.getElementById('nextBtn').onclick = () => { player.nextTrack(); };
    };
    {% endif %}
</script>
```

### Step 4: Styling (`styles.css`)

Modify `c:\Users\HP\Downloads\TEST1\static\styles.css`.

**Location**: Add to the very end of the file.

```css
/* SPOTIFY INTEGRATION */
.spotify-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 32px;
    text-align: center;
    margin-top: 32px; /* Space it out from timer if stacked, or adjust grid */
}

/* If you want it in the grid, add it to the layout in styles.css:
   Currently .study-mode-layout is 1fr 380px.
   You might want to stack it under the timer or todos.
*/

.btn-spotify {
    display: inline-block;
    background: #1DB954;
    color: white;
    padding: 12px 24px;
    border-radius: 30px;
    text-decoration: none;
    font-weight: 700;
    transition: transform 0.2s;
}

.btn-spotify:hover {
    transform: scale(1.05);
}

.player-controls {
    display: flex;
    justify-content: center;
    gap: 20px;
    margin: 15px 0;
}

.player-controls button {
    background: none;
    border: none;
    font-size: 28px;
    cursor: pointer;
    color: var(--text-primary);
    transition: color 0.2s;
}

.player-controls button:hover {
    color: var(--accent);
}
```
