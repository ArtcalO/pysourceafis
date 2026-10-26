# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
private vulnerability reporting ("Security" tab -> "Report a vulnerability")
on the project repository. You will get an answer within 7 days.

Include what you found, how to reproduce it (with synthetic data only, never
real fingerprints), and the affected versions.

## Supported versions

Only the latest released version receives security fixes while the project is 0.x.

## Handling biometric data

pysourceafis processes fingerprints, which are sensitive personal data in most
jurisdictions. The library itself stores nothing, but applications built on
it should:

- encrypt stored templates and images and restrict who can access them;
- never log images or templates;
- remember that a template is **not** anonymous and **cannot** be revoked like a password;
- obtain consent / a lawful basis before collecting fingerprints.

Fingerprint images alone do not prove that a live finger was present
(no liveness detection).
