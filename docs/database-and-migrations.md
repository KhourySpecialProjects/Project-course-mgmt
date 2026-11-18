# Database and migrations

The app stores its data in PostgreSQL. Python code talks to it through **SQLAlchemy** (an ORM: you work with Python classes instead of writing SQL by hand), and **Alembic** manages changes to the table structure over time.

## Key ideas

- A **model** is a Python class that describes a table. Example: [`api/app/users/models.py`](../api/app/users/models.py) defines the `users` table.
- A **migration** is a Python file in [`api/migrations/versions/`](../api/migrations/versions/) that changes the database structure, e.g. "create the `courses` table" or "add a `github_username` column to `users`".
- The database remembers which migrations it has applied (in a table called `alembic_version`). `alembic upgrade head` applies any that are missing.
- **Migrations run automatically** whenever the API container starts.

Changing a model does **not** change the database by itself. You must create a migration and apply it.

## Adding a table: worked example

Say you're adding courses.

### 1. Write the model

Create `api/app/courses/models.py`:

```python
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, TimestampMixin


class Course(TimestampMixin, Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)  # e.g. "CS4530"
    name: Mapped[str] = mapped_column(String(200))
    term: Mapped[str] = mapped_column(String(20))               # e.g. "Fall 2026"
```

Notes:

- `Mapped[str]` means the column is required (`NOT NULL`). Use `Mapped[str | None]` for optional columns.
- `TimestampMixin` adds `created_at` and `updated_at` automatically.
- Also create an empty `api/app/courses/__init__.py` so Python treats the folder as a package.

### 2. Register it

Import the model in [`api/app/models.py`](../api/app/models.py):

```python
from app.courses.models import Course
```

Alembic only sees models that are imported there.

### 3. Generate the migration

```bash
docker compose exec api alembic revision --autogenerate -m "add courses table"
```

(or `make migration m="add courses table"`)

Alembic compares your models with the live database and writes a new file in `api/migrations/versions/`.

### 4. Review the generated file

**Always open and read it.** Autogenerate is helpful but not perfect. Check that:

- `upgrade()` does what you expect, and nothing else.
- `downgrade()` undoes it.
- Renamed columns or tables appear as a rename, not as drop + add (which would delete data). Autogenerate can't detect renames; edit the file to use `op.alter_column(..., new_column_name=...)` or `op.rename_table(...)` instead.

### 5. Apply it

```bash
docker compose exec api alembic upgrade head
```

(or `make migrate`, or just restart the API container).

### 6. Commit the model and the migration together

Teammates get your migration when they pull, and their API container applies it on its next start.

## Useful Alembic commands

Run these with `docker compose exec api` in front:

| Command | What it does |
| ------- | ------------ |
| `alembic current` | Show which migration the database is at |
| `alembic history` | List all migrations |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Undo the most recent migration |
| `alembic revision -m "msg"` | Create an empty migration (for data changes you write by hand) |

## Querying data in Python

Inside an endpoint, ask for a `db: DbSession` parameter:

```python
from sqlalchemy import select

from app.core.db import DbSession

@router.get("/courses")
def list_courses(db: DbSession) -> list[Course]:
    return list(db.scalars(select(Course).order_by(Course.code)))

@router.post("/courses")
def create_course(body: CourseCreate, db: DbSession) -> Course:
    course = Course(**body.model_dump())
    db.add(course)
    db.commit()       # write to the database
    db.refresh(course)  # reload, e.g. to get the new id
    return course
```

Fetch one row by primary key with `db.get(Course, course_id)` (returns `None` if not found).

## Looking at the data directly

Open a SQL prompt in the database container:

```bash
make psql
```

or, without make:

```bash
docker compose exec db psql -U coursemgmt -d coursemgmt
```

Handy commands at the `coursemgmt=#` prompt: `\dt` (list tables), `\d users` (describe a table), `SELECT id, email, is_superuser FROM users;`, and `\q` (quit).

You can also connect a desktop tool such as [DBeaver](https://dbeaver.io), [TablePlus](https://tableplus.com), or VS Code's PostgreSQL extension to `localhost:5432` with the username, password, and database name from your `.env`.

## Starting over

To delete **all** local data and rebuild the database from the migrations:

```bash
docker compose down -v
```

```bash
docker compose up -d
```

The superuser is recreated from `.env` on start-up.
