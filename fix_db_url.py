#!/usr/bin/env python3
from urllib.parse import quote

# Original password
password = "W3llRecruit!ng2025#DB"

# Properly encode for URL
encoded_password = quote(password, safe='')

# Construct the correct DATABASE_URL
database_url = f"postgresql://citus:{encoded_password}@c-well-intake-db.kaj3v6jxajtw66.postgres.cosmos.azure.com:5432/citus?sslmode=require"

print(f"Original password: {password}")
print(f"Encoded password: {encoded_password}")
print(f"\nCorrect DATABASE_URL:")
print(database_url)