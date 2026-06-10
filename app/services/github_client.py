import httpx

from app.config import settings

# TODO: Truncate or split diffs exceeding ~100KB for production use.
# Large diffs may exceed Devin session context limits.


async def get_pr_diff(repo: str, pr_number: int) -> str:
    """Fetch the raw diff for a pull request."""
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers, timeout=60.0)
        resp.raise_for_status()
        return resp.text


async def post_review_comment(repo: str, pr_number: int, body: str) -> dict:
    """Post a comment on a pull request."""
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json={"body": body}, timeout=30.0)
        resp.raise_for_status()
        return resp.json()
