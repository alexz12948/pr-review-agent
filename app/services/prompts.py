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


def fix_single_prompt(finding: dict, diff: str, pr_metadata: dict) -> str:
    """Build a prompt for a fix agent that addresses a single finding."""
    repo = pr_metadata.get("repo", "")
    branch = pr_metadata.get("branch") or pr_metadata.get("head_ref") or "main"
    agent_type = finding.get("agent_type", "")
    severity_or_category = finding.get("severity") or finding.get("category") or "n/a"
    title = finding.get("title", "")
    description = finding.get("description", "")
    file = finding.get("file", "n/a")
    line = finding.get("line", "n/a")
    return f"""You are a code fix agent. You have access to the repository {repo} on branch {branch}.

A PR review found the following issue:
- Type: {agent_type}
- Severity/Category: {severity_or_category}
- Title: {title}
- Description: {description}
- File: {file}, Line: {line}

Original PR diff for context:
{diff}

Instructions:
1. Clone the repository and checkout branch {branch}
2. Navigate to the identified file and line
3. Implement a fix that addresses the finding
4. Ensure existing tests still pass
5. Commit with message: "fix: {title} [auto-fix]"
6. Push to the branch

Output JSON: {{"status": "fixed"|"skipped", "commit_sha": "...", "summary": "..."}}
"""


def fix_batch_prompt(findings_list: list[dict], diff: str, pr_metadata: dict) -> str:
    """Build a prompt for a fix agent that addresses multiple findings at once."""
    repo = pr_metadata.get("repo", "")
    branch = pr_metadata.get("branch") or pr_metadata.get("head_ref") or "main"

    lines = []
    for idx, finding in enumerate(findings_list, start=1):
        agent_type = finding.get("agent_type", "")
        severity_or_category = (
            finding.get("severity") or finding.get("category") or "n/a"
        )
        title = finding.get("title", "")
        description = finding.get("description", "")
        file = finding.get("file", "n/a")
        line = finding.get("line", "n/a")
        lines.append(
            f"""### Finding {idx} (id={finding.get("id")})
- Type: {agent_type}
- Severity/Category: {severity_or_category}
- Title: {title}
- Description: {description}
- File: {file}, Line: {line}"""
        )
    findings_block = "\n\n".join(lines) if lines else "(no findings provided)"

    return f"""You are a code fix agent. You have access to the repository {repo} on branch {branch}.

A PR review found the following {len(findings_list)} issue(s):

{findings_block}

Original PR diff for context:
{diff}

Instructions:
1. Clone the repository and checkout branch {branch}
2. Address every finding listed above
3. Implement fixes for each finding, navigating to the identified files and lines
4. Ensure existing tests still pass
5. Make one or more commits, each with a message describing the fix and ending in "[auto-fix]"
6. Push to the branch

Output JSON: {{"status": "fixed"|"skipped", "commit_sha": "...", "summary": "..."}}
"""
