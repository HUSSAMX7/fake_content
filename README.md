# صياغة — مولّد العروض الفنية

واجهة وAPI لتوليد عرض فني Word من ملفات موارد وتمبلت بعلامات `@...@@`.

## التشغيل المحلي

### Backend

```bash
uv sync
# ضع OPENAI_API_KEY و OPENROUTER_API_KEY في ملف .env (انظر .env.example)
# OPENROUTER_API_KEY مطلوب لتوليد الصور (Nano Banana 2 Lite)
uv run uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env.local   # اختياري
npm install
npm run dev
```

افتح http://localhost:3000

## API

| Method | Route | Body | Response |
|--------|-------|------|----------|
| GET | `/api/default-template` | — | ملف DOCX |
| POST | `/api/generate` | `multipart`: `resources` (PDF/DOCX)، `template` اختياري | ملف DOCX |
| GET | `/api/health` | — | `{ "status": "ok" }` |

بدون تسجيل دخول في هذه المرحلة.

## النشر على Render

المشروع جاهز عبر [`render.yaml`](render.yaml): خدمتان — `siyagha-api` (FastAPI) و`siyagha-web` (Next.js).

1. ادفع الكود إلى GitHub (كل الملفات بما فيها `backend/defaults/good_template.docx`).
2. في [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** → اختر الريبو.
3. بعد إنشاء الخدمات، عيّن المتغيرات:

| Service | Variable | Example |
|---------|----------|---------|
| `siyagha-api` | `OPENAI_API_KEY` | مفتاح OpenAI (النص) |
| `siyagha-api` | `OPENROUTER_API_KEY` | مفتاح OpenRouter (الصور) |
| `siyagha-api` | `CORS_ORIGINS` | `https://siyagha-web.onrender.com` |
| `siyagha-web` | `NEXT_PUBLIC_API_URL` | `https://siyagha-api.onrender.com` |

4. أعد Deploy للواجهة بعد ضبط `NEXT_PUBLIC_API_URL` (يُقرأ وقت الـ build).
5. افتح رابط `siyagha-web` وجرّب التوليد.

ملاحظات:
- الـ API على خطة **Starter** في الـ Blueprint لأن التوليد يحتاج ذاكرة أكبر من Free (512MB).
- Free للواجهة قد يدخل sleep بعد خمول؛ أول طلب بعد النوم يتأخر ~دقيقة.
- مهلة طلب Render تصل حتى ~100 دقيقة — مناسبة للتوليد الطويل نسبيًا.

### إذا فشل Deploy للواجهة بـ Timed out

على خدمة الواجهة (`syaghah` أو `siyagha-web`) في Render Dashboard → **Settings**:

| الإعداد | القيمة |
|---------|--------|
| Root Directory | `frontend` |
| Build Command | `chmod +x scripts/render-build.sh && ./scripts/render-build.sh` |
| Start Command | `npm run start` |
| Health Check Path | `/` |

وتأكد من وجود `NEXT_PUBLIC_API_URL` في **Environment** ثم **Clear build cache & deploy**.

إذا استمر الفشل: ارفع الخطة من **Free** إلى **Starter** (ذاكرة أكبر أثناء البناء والتشغيل).
