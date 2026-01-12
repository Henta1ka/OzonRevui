# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it by emailing the maintainer instead of using the issue tracker.

Please include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if available)

We take all security reports seriously and will respond as quickly as possible.

## Security Measures

### API Keys and Credentials
- All sensitive credentials (Ozon API key, OpenAI API key) are stored in `.env` file
- Never commit `.env` to version control
- Use environment variables for sensitive data in production
- Rotate keys regularly

### Database
- SQLite is used for local development
- For production deployment, consider upgrading to PostgreSQL
- Always use database backups

### Frontend Security
- User input is sanitized with `escapeHtml()` function to prevent XSS attacks
- All API calls use proper error handling

### Code Security
- No hardcoded secrets in the codebase
- All dependencies are pinned to specific versions in `requirements.txt`
- Regular dependency updates recommended

## Known Limitations

- This is a single-user application, not designed for multi-user authentication
- No built-in encryption for stored data (use HTTPS in production)
- Review status detection relies on Ozon API response format

## Best Practices for Deployment

1. Use HTTPS/TLS for all communications
2. Store `.env` file securely on the server
3. Restrict API access with authentication if exposed publicly
4. Keep dependencies updated
5. Monitor logs for suspicious activity
6. Use strong API keys from Ozon and OpenAI
