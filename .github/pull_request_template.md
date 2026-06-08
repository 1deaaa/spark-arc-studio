## Summary

Describe the maintainer or user problem this pull request solves.

> Branch target note: normal contribution PRs should target `dev` unless the maintainer explicitly asks for `main`.

## Scope

- Area touched:
- User-visible impact:
- Architectural touchpoints:

## SparkArc-specific checklist

- [ ] I checked whether this change should extend an existing pipeline, facade, or shared infrastructure instead of introducing a parallel path
- [ ] I did not mix chat NDJSON behavior with business SSE / semantic-stream behavior
- [ ] I reused existing tool, patch, or chunking infrastructure where applicable
- [ ] I kept temporary outputs out of tracked test directories and used `/.tmp/` for generated artifacts
- [ ] I updated frontend i18n strings if I added or changed user-visible text

## Agent / tool / registry impact

Complete this section when relevant.

- [ ] No agent changes
- [ ] Agent prompt modality changed
- [ ] Tool registration changed
- [ ] Director delegation or routing changed
- [ ] Frontend agent mapping changed

Notes:

## Testing

List the exact commands you ran.

```bash
```

## Screenshots / logs / reproduction notes

Add screenshots, terminal output summaries, or reproduction notes when they materially help review.

## Additional context

Anything reviewers should watch for, including migration impact, legal/operator-facing changes, or rollout concerns.
