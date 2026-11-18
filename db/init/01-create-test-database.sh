#!/bin/sh
# Runs once, the first time the Postgres container starts with an empty volume.
# Creates a second database used only by the automated tests, so running the
# tests never touches your development data.
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-SQL
  CREATE DATABASE ${POSTGRES_DB}_test OWNER $POSTGRES_USER;
SQL
