# מפרט טכני (Technical Specification)

**מערכת חכמה לניהול משימות**  
**גרסה:** 1.0  
**תאריך:** 17 במרץ 2026  
**מחבר:** Grok

## 1. סקירה כללית

מערכת חכמה לניהול משימות היא פלטפורמה מבוססת-ענן שמטרתה לסייע לצוותים (בעיקר צוותי פיתוח, שיווק, ניהול פרויקטים ועסקים קטנים) לנהל משימות בצורה יעילה, חכמה וממוקדת יותר.

מאפיינים עיקריים:
- סדר עדיפויות אוטומטי מבוסס AI
- חיזוי זמני סיום משימות
- לוחות Kanban + רשימות + תצוגת לוח שנה
- שיתוף פעולה בזמן אמת ועדכונים מיידיים
- התראות חכמות וסיכומים יומיים
- דוחות התקדמות וזיהוי צווארי בקבוק

המערכת נועדה להפחית עומס קוגניטיבי, לשפר שקיפות ולקצר זמני ביצוע משימות.

## 2. ארכיטקטורת מערכת

המערכת מבוססת על **ארכיטקטורת מיקרו-שירותים** (Microservices) עם גישה מודרנית ומדרגית.

### רכיבים עיקריים
- **API Gateway** – נקודת כניסה יחידה (Kong / Traefik / Nginx)
- **שירותי ליבה**:
  - שירות משתמשים ואימות (User & Auth Service)
  - שירות משימות (Task Service)
  - שירות קטגוריות ותיוגים חכמים (Category & Smart Tagging Service)
  - שירות התראות ו-WebSockets (Notification Service)
  - שירות אנליטיקה ו-AI (Analytics & Intelligence Service)
- **Event Bus** – RabbitMQ או Redis Streams להעברת אירועים אסינכרונית
- **Frontend** – אפליקציית Single Page Application
- **אחסון** – PostgreSQL (עם אפשרות ל-NoSQL נוסף בעתיד לשימושי AI)
- **סביבת ריצה** – Docker + Kubernetes

יתרונות הארכיטקטורה:
- מדרגיות עצמאית לכל שירות
- פריסה עצמאית ומהירה
- בידוד תקלות
- אפשרות להחלפת טכנולוגיה בשירות ספציפי בעתיד

## 3. מבנה בסיס הנתונים (טבלאות מרכזיות)

המערכת משתמשת ב-**PostgreSQL** כבסיס נתונים ראשי.

```sql
-- משתמשים
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(120),
    role VARCHAR(30) DEFAULT 'developer',  -- admin, manager, developer, viewer
    team_id BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- משימות
CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    title VARCHAR(300) NOT NULL,
    description TEXT,
    status VARCHAR(30) DEFAULT 'todo',     -- todo, doing, review, done
    priority VARCHAR(20) DEFAULT 'medium', -- low, medium, high, urgent
    assignee_id BIGINT REFERENCES users(id),
    category_id BIGINT REFERENCES categories(id),
    due_date DATE,
    estimated_hours NUMERIC(6,2),
    actual_hours NUMERIC(6,2),
    ai_priority_score NUMERIC(5,3),        -- ציון עדיפות מחושב על ידי AI
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- קטגוריות / תגיות
CREATE TABLE categories (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    color_hex CHAR(7) DEFAULT '#2563eb',
    created_by BIGINT REFERENCES users(id),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
הערות:

שימוש ב-TIMESTAMPTZ (זמן עם אזור) – הכל ב-UTC
אינדקסים על: status, priority, assignee_id, due_date, category_id
שדה JSONB נוסף ב-tasks לשמירת מטא-דאטה של AI

4. אבטחת מידע
אימות

JWT Bearer Token (גישה: 15 דק', רענון: 14 יום)
תמיכה ב-OAuth2 (Google, Microsoft, GitHub)
אפשרות 2FA (TOTP)

הצפנה והגנות

HTTPS בלבד (TLS 1.3)
bcrypt / Argon2id להצפנת סיסמאות
הצפנת שדות רגישים בטבלה (pgcrypto)
Rate Limiting + IP blocking
CORS מוגבל מאוד
Input validation קפדני (Pydantic / Zod)
OWASP Top 10 מכוסה במלואו
Audit log מלא על פעולות רגישות

גישה

RBAC + Scope-based permissions
כל שירות בודק הרשאות באופן עצמאי (zero-trust)

5. טכנולוגיות נבחרות

Backend: Python 3.11+ + FastAPI
Frontend: React 18 + TypeScript + Tailwind CSS + Zustand / Redux Toolkit
בסיס נתונים: PostgreSQL 16
ORM / Migrations: SQLAlchemy 2.0 + Alembic
אימות: PyJWT + python-jose
זמן אמת: WebSockets (FastAPI) + Redis
תורים ואירועים: RabbitMQ או Redis
AI: scikit-learn / LightGBM + Hugging Face (למודלים קטנים)
קונטיינרים: Docker + Docker Compose (dev) / Kubernetes (prod)
CI/CD: GitHub Actions
ניטור: Prometheus + Grafana + Sentry

text