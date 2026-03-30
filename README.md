# 🎓 EduNexus — Production Deployment Guide

## 📁 Files
```
edunexus/
├── app.py                 ← Flask backend (all APIs + auth)
├── requirements.txt       ← Python packages
├── render.yaml            ← Render config
├── build.sh               ← Build script
├── .env.example           ← Environment variables template
└── templates/
    ├── landing.html       ← Landing page (/)
    ├── auth.html          ← Login + Register + OTP
    └── dashboard.html     ← Main app
```

---

## 🗄️ STEP 1 — MySQL Database (Aiven - Free)

1. Go to **https://aiven.io** → Sign up free
2. Create **MySQL** service → Free tier
3. Wait for it to start → Click **Overview**
4. Note these values:
   - **Host** (e.g. `mysql-xxx.aivencloud.com`)
   - **Port** (e.g. `14567`)
   - **User** (`avnadmin`)
   - **Password** (shown in overview)
   - **Database** name (`defaultdb` or create `edunexus`)

---

## 📧 STEP 2 — Gmail App Password

1. Go to your **Gmail** → **Google Account Settings**
2. **Security** → Enable **2-Step Verification** (if not done)
3. **Security** → **App Passwords**
4. Select app: **Mail**, device: **Other** → type `EduNexus`
5. Copy the **16-character password** (e.g. `xxxx xxxx xxxx xxxx`)

---

## 🚀 STEP 3 — Deploy on Render

1. Push this code to **GitHub**:
```bash
git init
git add .
git commit -m "EduNexus initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/edunexus.git
git push -u origin main
```

2. Go to **https://render.com** → Sign up/Login
3. Click **New +** → **Web Service**
4. Connect your GitHub repo
5. Settings:
   - **Name**: edunexus
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT`

6. **Environment Variables** — Add these:

| Key | Value |
|-----|-------|
| `SECRET_KEY` | any-long-random-string-here |
| `DB_HOST` | your-aiven-host |
| `DB_PORT` | your-aiven-port |
| `DB_USER` | avnadmin |
| `DB_PASSWORD` | your-aiven-password |
| `DB_NAME` | defaultdb |
| `MAIL_USERNAME` | yourgmail@gmail.com |
| `MAIL_PASSWORD` | xxxx-xxxx-xxxx-xxxx |

7. Click **Create Web Service** → Wait 2-3 minutes

---

## ✅ Done!

Your app will be live at: `https://edunexus.onrender.com`

- `/` → Landing page
- `/login` → Sign in
- `/register` → Create account (OTP email sent)
- `/dashboard` → Main app

---

## ⚠️ Notes

- **First deploy** automatically creates all DB tables
- **Free Render** sleeps after 15min inactivity (first request is slow)
- **Gmail App Password** ≠ your Gmail password
- Aiven free tier = 1 month trial, then use PlanetScale or Railway MySQL
