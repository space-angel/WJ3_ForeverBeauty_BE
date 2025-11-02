#!/bin/bash
export DATABASE_URL="postgresql://postgres.mmxrpywlscvaoyxlcyin:aslf2k34jbb32k4hb32b4hb@aws-1-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require"
uvicorn app.main:app --port 8000