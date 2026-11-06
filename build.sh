#!/usr/bin/env bash
# Exit on error
set -o errexit

echo "--- 1. Building React Frontend ---"
cd frontend
npm install
npm run build
cd ..

echo "--- 2. Installing Python Dependencies ---"
pip install -r requirements.txt

echo "--- 3. Collecting Static Files ---"
python backend/manage.py collectstatic --noinput

echo "--- 4. Applying Database Migrations ---"
python backend/manage.py migrate --noinput

echo "--- 5. Loading Converted Initial Data if DB is Empty ---"
python backend/manage.py load_initial_data

echo "--- Build Finished Successfully ---"

