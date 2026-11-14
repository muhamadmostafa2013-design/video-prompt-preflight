# Security

Do not include API keys, private prompts, personal data, or unpublished media in issues.
For security-sensitive reports, contact the maintainers privately rather than opening a public issue.

## v0.5.3 privacy and trust boundaries

- Static browser mode runs locally; no video upload endpoint exists. Local Failure Memory uses browser storage and may include personal information. Users should delete entries on shared computers.
- Python media probes restrict FFmpeg media protocols to file/pipe, and optional OCR/ASR work on local media. Treat untrusted video decoders as a third-party attack surface; run with least privilege and avoid exposing sensitive directories.
- `jev-review` can transmit prompt data to a remote model/SDK. It is disabled unless `--allow-remote-judge` is passed. This flag authorizes transmission but does not independently guarantee the privacy practices of any provider.
- Local report JSON may include recognized speech and screen text. Do not upload sensitive reports to issue trackers.
- CSP and DOM escaping reduce browser injection risks but do not replace an external penetration test.
