# MediaVault — All-in-One Media Studio

**MediaVault** is a full-stack web application built with **Flask**, **FFmpeg (`imageio-ffmpeg`)**, and a mobile-optimized **Vanilla JS / HTML5 / CSS3** studio interface.

---

## Project Folder Structure (GitHub Root)

Keep all files in the main root folder of your GitHub repository:

```text
mediavault/
├── app.py              # Flask backend API & FFmpeg MP3 converter
├── index.html          # Premium single-file frontend dashboard
├── requirements.txt    # Python libraries for Render (Flask, Gunicorn, FFmpeg)
├── render.yaml         # Automatic Render deployment configuration
├── .gitignore          # Prevents temporary uploads & cache from pushing to GitHub
└── README.md           # Project documentation
```

---

## How to Deploy on Render (Step-by-Step)

### Option 1: Manual Web Service Setup on Render
1. Upload `app.py`, `index.html`, `requirements.txt`, `render.yaml`, `.gitignore`, and `README.md` to your **GitHub repository**.
2. Log in to [Render.com](https://render.com/) and click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. Fill in the following settings:
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**:
     ```bash
     gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 2 --timeout 200
     ```
5. Select the **Free** plan (or any paid plan) and click **Create Web Service**.

### Option 2: Automatic Blueprint Setup (`render.yaml`)
1. On your Render Dashboard, click **New +** -> **Blueprint**.
2. Select your GitHub repository.
3. Render will automatically read `render.yaml` and configure the server, health check (`/api/health`), and timeout settings.

---

## API Endpoints

- `GET /` — Serves the `index.html` MediaVault Studio UI
- `GET /api/health` — Returns live server status and FFmpeg readiness
- `POST /api/detect` — Inspects Instagram, Facebook, and YouTube links
- `POST /api/convert` — Converts uploaded video/audio files (up to 100 MB) to 192kbps stereo MP3
