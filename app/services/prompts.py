import json


def security_prompt(diff: str, pr_metadata: dict) -> str:
    """Build a prompt for the security review agent."""
    meta_json = json.dumps(pr_metadata, indent=2)
    return f"""You are a senior security engineer reviewing a pull request.

## PR Metadata
{meta_json}

## Diff
```diff
{diff}
```

## Instructions
Analyze the diff above for security issues. Focus on:
- Authentication and authorization gaps
- Injection vectors (SQL injection, XSS, command injection, etc.)
- Insecure defaults or misconfigurations
- Privilege escalation risks
- Secrets or credentials exposed in code
- Unsafe deserialization or input handling

## Required Output Format
Respond with ONLY a JSON object (no markdown fences, no extra text):
{{
  "findings": [
    {{
      "severity": "critical|high|medium|low",
      "title": "Short title",
      "description": "Detailed explanation of the issue and remediation",
      "file": "path/to/file.py",
      "line": 42
    }}
  ],
  "summary": "One-paragraph summary of the security posture of this PR"
}}

If no issues are found, return an empty findings array with a summary noting the PR looks clean.
"""


def quality_prompt(diff: str, pr_metadata: dict) -> str:
    """Build a prompt for the code quality review agent."""
    meta_json = json.dumps(pr_metadata, indent=2)
    return f"""You are a senior software engineer reviewing a pull request for code quality.

## PR Metadata
{meta_json}

## Diff
```diff
{diff}
```

## Instructions
Analyze the diff above for code quality issues. Focus on:
- Logic bugs or off-by-one errors
- Inconsistencies with surrounding code patterns
- Missing error handling or edge cases
- Missing or inadequate test coverage
- Sparse or misleading PR description / comments
- Performance concerns or unnecessary complexity

## Required Output Format
Respond with ONLY a JSON object (no markdown fences, no extra text):
{{
  "findings": [
    {{
      "category": "bug|consistency|error-handling|testing|documentation|performance",
      "title": "Short title",
      "description": "Detailed explanation and suggested fix",
      "file": "path/to/file.py",
      "line": 42
    }}
  ],
  "suggested_description": "Optional: a better PR description if the current one is sparse",
  "summary": "One-paragraph summary of the code quality of this PR"
}}

If no issues are found, return an empty findings array with a positive summary.
"""


def synthesis_prompt(security_output: str, quality_output: str, pr_metadata: dict) -> str:
    """Build a prompt for the synthesis agent that combines both reviews."""
    meta_json = json.dumps(pr_metadata, indent=2)
    return f"""You are a technical writer synthesizing two code review reports into a single, \
well-structured GitHub PR review comment.

## PR Metadata
{meta_json}

## Security Review Output
{security_output}

## Code Quality Review Output
{quality_output}

## Instructions
Combine the above two reviews into a single structured Markdown comment suitable \
for posting on a GitHub pull request. The comment should include:

1. **Header** — "## 🔍 Automated PR Review" with the PR title
2. **Security Findings Table** — columns: Severity, Title, File, Line, Description. \
If no findings, state "No security issues found."
3. **Code Quality Findings Table** — columns: Category, Title, File, Line, Description. \
If no findings, state "No quality issues found."
4. **Summary** — a brief paragraph synthesizing both reviews, noting overall risk level \
and any recommended actions.

## Required Output Format
Respond with ONLY the Markdown text (no JSON wrapping, no code fences around the whole response). \
The output should be ready to post directly as a GitHub comment.
"""
