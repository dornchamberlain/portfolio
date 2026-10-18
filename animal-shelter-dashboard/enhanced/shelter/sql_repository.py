# Store shelter outcome records in SQLite and keep query choices under application control.
from contextlib import contextmanager
from dataclasses import dataclass
import logging
import math
from collections.abc import Mapping

from sqlalchemy import (MetaData, Table, Column, String, Float, CheckConstraint,
                        Index, create_engine, select, func, case, insert, update, delete, event)
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from .records import FIELDS
from .repository import RepositoryError
from .filters import validate_profile
from .ranking import SCORING_PROFILES, score_candidate

logger = logging.getLogger(__name__)
metadata = MetaData()
animals = Table(
    "animal_records", metadata,
    Column("id", String(120), primary_key=True, nullable=False),
    *[Column(name, String(200), nullable=True) for name in FIELDS[:5]],
    *[Column(name, Float, nullable=True) for name in FIELDS[5:]],
    CheckConstraint("length(trim(id)) BETWEEN 1 AND 120", name="valid_record_id"),
    CheckConstraint("age_upon_outcome_in_weeks BETWEEN 0 AND 1.7976931348623157e308", name="nonnegative_age"),
    CheckConstraint("location_lat BETWEEN -90 AND 90", name="valid_latitude"),
    CheckConstraint("location_long BETWEEN -180 AND 180", name="valid_longitude"),
)
for name in FIELDS[5:]:
    animals.append_constraint(CheckConstraint(
        f"{name} IS NULL OR typeof({name}) IN ('integer', 'real')", name=f"numeric_{name}"))
# Outcome records can repeat animal IDs. Only the record ID is unique.
for name in FIELDS[:5]:
    animals.append_constraint(CheckConstraint(
        f"{name} IS NULL OR length(trim({name})) BETWEEN 1 AND 200",
        name=f"valid_{name}"))
# This order supports animal-type searches followed by breed and stable record ID.
Index("ix_type_breed_id", animals.c.animal_type, animals.c.breed, animals.c.id)


@dataclass
class Page:
    rows: list[dict]
    total: int
    page: int
    page_size: int


def validate_values(values, partial=False):
    # Reject bad writes instead of silently changing a supplied value to unknown.
    if not isinstance(values, Mapping) or not values:
        raise ValueError("Supply a nonempty record object.")
    allowed = set(FIELDS) if partial else {"id", *FIELDS}
    if set(values) - allowed:
        raise ValueError("Record contains unsupported fields.")
    if not partial and "id" not in values:
        raise ValueError("A record ID is required.")
    clean = {}
    for key, value in values.items():
        if key in FIELDS[5:]:
            if value is not None:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Numeric fields must be finite numbers or null.")
                if ((key == FIELDS[5] and value < 0) or
                    (key == "location_lat" and not -90 <= value <= 90) or
                    (key == "location_long" and not -180 <= value <= 180)):
                    raise ValueError("Age or coordinates are outside the allowed range.")
        elif value is not None:
            if not isinstance(value, str) or not value.strip() or len(value.strip()) > (120 if key == "id" else 200):
                raise ValueError("Text fields must contain bounded, nonempty text or null.")
            value = value.strip()
        elif key == "id":
            raise ValueError("A record ID is required.")
        clean[key] = value
    if not partial:
        clean = {key: clean.get(key) for key in ("id", *FIELDS)}
    return clean


class SQLiteRepository:
    def __init__(self, path):
        self.engine = create_engine(URL.create("sqlite", database=str(path)),
                                    connect_args={"timeout": 5})
        # Explicit BEGIN gives the count and page queries the same read snapshot.
        @event.listens_for(self.engine, "connect")
        def connect(dbapi_connection, connection_record):
            dbapi_connection.isolation_level = None

        @event.listens_for(self.engine, "begin")
        def begin(connection):
            connection.exec_driver_sql("BEGIN")

    @contextmanager
    def transaction(self):
        # Each operation owns a short transaction; failed writes roll back together.
        try:
            with self.engine.begin() as connection:
                yield connection
        except IntegrityError:
            raise RepositoryError("Record conflicts with a database constraint.") from None
        except SQLAlchemyError as exc:
            logger.warning("SQLite operation failed (%s)", type(exc).__name__)
            raise RepositoryError("Database operation failed. Check the SQLite file and schema.") from None

    def initialize(self):
        # Schema creation is an explicit setup step, not an import-time side effect.
        with self.transaction() as connection:
            metadata.create_all(connection)

    def create_many(self, records):
        clean = [validate_values(row) for row in records]
        if clean:
            with self.transaction() as connection:
                connection.execute(insert(animals), clean)
        return len(clean)

    def create(self, record):
        self.create_many([record])
        return record["id"].strip()

    def update(self, record_id, changes):
        key = validate_values({"id": record_id})["id"]
        clean = validate_values(changes, partial=True)
        with self.transaction() as connection:
            return connection.execute(update(animals).where(animals.c.id == key).values(**clean)).rowcount == 1

    def delete(self, record_id):
        key = validate_values({"id": record_id})["id"]
        with self.transaction() as connection:
            return connection.execute(delete(animals).where(animals.c.id == key)).rowcount == 1

    def read_page(self, *, profile="RESET", filters=None, sort="rank", descending=False,
                  page=0, page_size=10, fields=None):
        validate_profile(profile)
        if type(page) is not int or not 0 <= page <= 1_000_000:
            raise ValueError("Page must be an integer from 0 to 1000000.")
        if type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("Page size must be an integer from 1 to 100.")
        if type(descending) is not bool:
            raise ValueError("Sort direction must be true or false.")
        if not isinstance(sort, str) or sort not in {"rank", "name", "breed", "id", "animal_id", "age_upon_outcome_in_weeks"}:
            raise ValueError("Unsupported sort field.")
        if fields is None:
            fields = ["id", *FIELDS]
        if (not isinstance(fields, (list, tuple)) or not fields or
            any(not isinstance(f, str) or f not in animals.c for f in fields) or len(set(fields)) != len(fields)):
            raise ValueError("Unsupported selected fields.")
        filters = {} if filters is None else filters
        if not isinstance(filters, Mapping) or set(filters) - {"animal_type", "breed", "sex_upon_outcome", "min_age", "max_age"}:
            raise ValueError("Unsupported filter field.")
        conditions = []
        for key, value in filters.items():
            if key in {"min_age", "max_age"}:
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                    raise ValueError("Age filters must be finite nonnegative numbers.")
                conditions.append(animals.c.age_upon_outcome_in_weeks >= value if key == "min_age"
                                  else animals.c.age_upon_outcome_in_weeks <= value)
            else:
                clean = validate_values({key: value}, partial=True)[key]
                conditions.append(animals.c[key] == clean)
        if filters.get("min_age", 0) > filters.get("max_age", math.inf):
            raise ValueError("Minimum age cannot exceed maximum age.")
        if profile != "RESET":
            conditions.append(animals.c.animal_type == "Dog")
            rules = SCORING_PROFILES[profile]
            score = (case((animals.c.breed.in_(sorted(rules.breeds)), rules.weights[0]), else_=0) +
                     case((animals.c.age_upon_outcome_in_weeks.between(rules.min_age, rules.max_age), rules.weights[1]), else_=0) +
                     case((animals.c.sex_upon_outcome == rules.sex, rules.weights[2]), else_=0))
            order = [score.desc(), animals.c.animal_id.is_(None), animals.c.animal_id, animals.c.id]
            # Assign ranks across the matching set before LIMIT. Ranking one page would be misleading.
            source = select(animals, score.label("score"),
                            func.row_number().over(order_by=order).label("rank")).where(*conditions).subquery()
        else:
            source = select(animals).where(*conditions).subquery()
        selected = list(fields)
        if profile != "RESET":
            selected += ["score", "rank"]
        statement = select(*(source.c[name] for name in selected))
        sort_column = source.c.rank if sort == "rank" and profile != "RESET" else source.c["id" if sort == "rank" else sort]
        statement = statement.order_by(sort_column.is_(None), sort_column.desc() if descending else sort_column.asc(), source.c.id)
        with self.transaction() as connection:
            total = connection.scalar(select(func.count()).select_from(animals).where(*conditions))
            # Clamp a stale page after deletes or changed filters to the last available page.
            page = min(page, max(0, (total - 1) // page_size))
            rows = [dict(row) for row in connection.execute(statement.limit(page_size).offset(page * page_size)).mappings()]
        if profile != "RESET" and all(f in fields for f in ("breed", "sex_upon_outcome", "age_upon_outcome_in_weeks")):
            # Reuse the tested explanation logic only for the returned page.
            rows = [score_candidate(row, rules) for row in rows]
        return Page(rows, total, page, page_size)

    def close(self):
        self.engine.dispose()
