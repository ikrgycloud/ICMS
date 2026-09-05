# Applicant Document Storage

Applicant documents are private. When `S3_BUCKET` is set, new uploads are
stored in that bucket and the database stores only an `s3://` object reference.
The reviewer opens documents through the authenticated ICMS API; bucket objects
do not need to be public.

Add these entries to `backend/.env`, each on one line in `KEY=value` form:

```dotenv
S3_BUCKET=your-private-admissions-bucket
S3_REGION=ap-south-1
# Leave blank for AWS S3. Set only for an S3-compatible provider such as MinIO.
S3_ENDPOINT_URL=
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
```

The IAM principal needs only `s3:PutObject` and `s3:GetObject` for the
`admissions/*` prefix in that bucket. The application sends uploads using
server-side encryption (`AES256`).

For local development, leave `S3_BUCKET` empty. Files are stored under
`backend/uploads/admissions`, which is not suitable for production.
