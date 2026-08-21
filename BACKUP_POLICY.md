# Backup and restoration policy

## PostgreSQL

Enable Railway's encrypted daily PostgreSQL backups and retain at least seven days. The production owner reviews backup completion weekly.

Create a scheduled Railway job once each week that runs `pg_dump` against the production database, compresses the result, and uploads it to a private, encrypted object-storage bucket. Give the job the minimum database and bucket permissions needed. Store the backup key and database credentials only in Railway variables.

## Restore verification

At least quarterly, restore the latest backup into a separate staging Railway database. Run migrations, start the API against that database, and verify a sample user, confirmed beauty profile, cart, and order can be read. Record the date, operator, backup identifier, duration, and result in the operations log. Never restore a production backup over production as a test.

## Recovery procedure

1. Declare the incident and stop writes if data corruption is suspected.
2. Choose the latest known-good Railway snapshot or weekly encrypted dump.
3. Restore first into staging and validate the application and migration version.
4. Obtain release-owner approval before production restoration.
5. Restore, rotate exposed credentials if applicable, validate health checks, and document the outcome.

Keep backups for the configured retention period, restrict access to the production owner and on-call engineer, and delete obsolete manual backups according to the storage retention rule.
