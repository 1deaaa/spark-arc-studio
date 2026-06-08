# Security Policy

## Supported code line

SparkArc is maintained as a moving mainline project. Security fixes are most likely to land on the current default branch first.

If you operate a fork, self-hosted deployment, or a modified white-label derivative, you are responsible for tracking upstream fixes and validating your own deployment posture.

## Reporting a vulnerability

Please **do not** open a public GitHub issue for a vulnerability that could expose users, operators, secrets, or infrastructure.

For private disclosure, contact the maintainer with:

- A concise summary of the issue
- Affected area and deployment context
- Reproduction steps or proof of concept
- Impact assessment
- Any logs, screenshots, or traces needed to validate the problem

If you already have a maintainer contact channel, use that private channel first. If not, open a minimal public issue only to request a private handoff, and avoid including exploit details.

## Scope examples

Examples of security-relevant reports in this repository:

- Authentication or account-boundary bypass
- Unauthorized access to project data, chat history, or generated content
- Secret exposure involving `LLM_KEY`, provider keys, or operator credentials
- Cross-user leakage in agent, project, or runtime state
- Unsafe default exposure in public/self-hosted deployment guidance
- Vulnerabilities introduced by packaging or release automation

Non-security issues that usually belong in normal issue reports:

- General feature requests
- Ordinary UI defects
- Non-sensitive test failures
- Documentation mistakes without security impact

## Disclosure expectations

Please allow the maintainer reasonable time to investigate, reproduce, and patch the issue before public disclosure.

Because SparkArc is also designed for self-hosting and third-party operation, a fix may require both code changes and operator guidance. Coordinated disclosure helps avoid exposing downstream users before mitigations exist.

## Operator reminder

If you run a public or semi-public SparkArc deployment, you are responsible for your own security controls, including but not limited to:

- HTTPS
- registration abuse controls
- access control
- firewall / reverse-proxy rate limiting
- key management
- backups
- moderation and compliance workflows

See the repository legal and operator guidance for additional boundaries.
