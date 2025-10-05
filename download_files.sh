#!/bin/bash
mkdir -p /mnt/data
cd /mnt/data
# SAS token - use environment variable if set, otherwise use default
# To override: export AZURE_SAS_TOKEN="your-new-sas-token"
SAS="${AZURE_SAS_TOKEN:-se=2025-09-12T23%3A59%3A59Z&sp=r&sv=2022-11-02&sr=c&sig=1SEOSJkGk%2B5llshpZHAdhbXge%2B5ttXuLhUqX%2Bfb5BRc%3D}"
curl -o "Deals_2025_09_10_2.csv" "https://wellintakestorage0903.blob.core.windows.net/imports/Deals_2025_09_10_2.csv?$SAS"
curl -o "Deals_Stage_History_2025_09_10.csv" "https://wellintakestorage0903.blob.core.windows.net/imports/Deals_Stage_History_2025_09_10.csv?$SAS"
curl -o "Meetings_2025_09_10_2.csv" "https://wellintakestorage0903.blob.core.windows.net/imports/Meetings_2025_09_10_2.csv?$SAS"
curl -o "Notes_Deals_2025_09_10.csv" "https://wellintakestorage0903.blob.core.windows.net/imports/Notes_Deals_2025_09_10.csv?$SAS"
ls -la /mnt/data/
echo "Files downloaded to /mnt/data/"
