"""
No-OAuth Reddit scraper using public .json endpoints.
No API keys required - uses Reddit's public JSON interface.

Note: This approach is subject to rate limiting and may be blocked by Reddit.
For production use, consider using the official Reddit API with OAuth.
"""
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

from utils.console import print_substep


# Default User-Agent - customize this to avoid rate limiting
DEFAULT_USER_AGENT = "python:reddit_video_bot:1.0 (no-oauth scraper)"

# Reddit base URLs
REDDIT_BASES = ["https://www.reddit.com", "https://old.reddit.com"]


class RedditScraperError(Exception):
    """Exception raised for Reddit scraper errors."""
    pass


@dataclass
class RedditPost:
    """Represents a Reddit post/submission."""
    id: str
    name: str  # t3_xxx
    title: str
    selftext: str
    author: str
    created_utc: float
    score: int
    upvote_ratio: float
    num_comments: int
    permalink: str
    url: str
    over_18: bool
    stickied: bool
    subreddit: str

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> "RedditPost":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            title=data.get("title", ""),
            selftext=data.get("selftext", ""),
            author=data.get("author", "[deleted]"),
            created_utc=float(data.get("created_utc", 0)),
            score=int(data.get("score", 0)),
            upvote_ratio=float(data.get("upvote_ratio", 0)),
            num_comments=int(data.get("num_comments", 0)),
            permalink=data.get("permalink", ""),
            url=data.get("url", ""),
            over_18=bool(data.get("over_18", False)),
            stickied=bool(data.get("stickied", False)),
            subreddit=data.get("subreddit", ""),
        )


@dataclass
class RedditComment:
    """Represents a Reddit comment."""
    id: str
    name: str  # t1_xxx
    body: str
    author: str
    created_utc: float
    score: int
    permalink: str
    parent_id: str
    link_id: str
    depth: int
    stickied: bool

    @classmethod
    def from_json(cls, data: Dict[str, Any], depth: int = 0) -> "RedditComment":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            body=data.get("body", ""),
            author=data.get("author", "[deleted]"),
            created_utc=float(data.get("created_utc", 0)),
            score=int(data.get("score", 0)),
            permalink=data.get("permalink", ""),
            parent_id=data.get("parent_id", ""),
            link_id=data.get("link_id", ""),
            depth=depth,
            stickied=bool(data.get("stickied", False)),
        )


class RedditScraper:
    """
    No-OAuth Reddit scraper using public .json endpoints.

    Example usage:
        scraper = RedditScraper()
        posts = scraper.get_subreddit_posts("AskReddit", limit=25, sort="hot")
        post, comments = scraper.get_post_with_comments(posts[0].id)
    """

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        base_url: str = REDDIT_BASES[0],
        request_delay: float = 2.0,
        timeout: float = 30.0,
        max_retries: int = 5,
    ):
        """
        Initialize the Reddit scraper.

        Args:
            user_agent: User-Agent string for requests
            base_url: Reddit base URL (www.reddit.com or old.reddit.com)
            request_delay: Delay between requests in seconds
            timeout: Request timeout in seconds
            max_retries: Maximum number of retries per request
        """
        self.user_agent = user_agent
        self.base_url = base_url.rstrip("/")
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = requests.Session()
        self._last_request_time = 0.0

    def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def _fetch_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Fetch JSON from a Reddit endpoint with retries and rate limiting.

        Args:
            url: Full URL to fetch
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            RedditScraperError: If request fails after retries
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }

        if params is None:
            params = {}
        params["raw_json"] = 1  # Get unescaped JSON

        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            self._rate_limit()

            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    print_substep(f"Rate limited. Waiting {retry_after}s...", style="yellow")
                    time.sleep(max(self.request_delay, retry_after))
                    last_error = RedditScraperError(f"Rate limited (429)")
                    continue

                # Handle server errors
                if 500 <= response.status_code < 600:
                    wait_time = self.request_delay * (attempt + 1)
                    print_substep(f"Server error {response.status_code}. Retrying in {wait_time}s...", style="yellow")
                    time.sleep(wait_time)
                    last_error = RedditScraperError(f"Server error: {response.status_code}")
                    continue

                # Handle other errors
                if response.status_code != 200:
                    raise RedditScraperError(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )

                return response.json()

            except requests.exceptions.RequestException as e:
                last_error = e
                wait_time = self.request_delay * (attempt + 1)
                if attempt < self.max_retries - 1:
                    print_substep(f"Request failed: {e}. Retrying in {wait_time}s...", style="yellow")
                    time.sleep(wait_time)
                continue

        raise RedditScraperError(f"Failed after {self.max_retries} attempts: {last_error}")

    def get_subreddit_posts(
        self,
        subreddit: str,
        sort: str = "hot",
        limit: int = 25,
        time_filter: str = "all",
        after: Optional[str] = None,
    ) -> List[RedditPost]:
        """
        Get posts from a subreddit.

        Args:
            subreddit: Subreddit name (without r/ prefix)
            sort: Sort method (hot, new, top, rising, controversial)
            limit: Maximum number of posts to retrieve (max 100 per request)
            time_filter: Time filter for top/controversial (hour, day, week, month, year, all)
            after: Pagination cursor (fullname of last item)

        Returns:
            List of RedditPost objects
        """
        # Clean subreddit name
        subreddit = subreddit.strip()
        if subreddit.lower().startswith("r/"):
            subreddit = subreddit[2:]

        url = f"{self.base_url}/r/{subreddit}/{sort}.json"
        params: Dict[str, Any] = {"limit": min(limit, 100)}

        if sort in ("top", "controversial"):
            params["t"] = time_filter
        if after:
            params["after"] = after

        data = self._fetch_json(url, params)

        posts = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            if child.get("kind") != "t3":
                continue
            post_data = child.get("data", {})
            if post_data:
                posts.append(RedditPost.from_json(post_data))

        return posts

    def get_post_by_id(self, post_id: str) -> Optional[RedditPost]:
        """
        Get a single post by ID.

        Args:
            post_id: Post ID (without t3_ prefix)

        Returns:
            RedditPost object or None if not found
        """
        # Remove t3_ prefix if present
        if post_id.startswith("t3_"):
            post_id = post_id[3:]

        url = f"{self.base_url}/comments/{post_id}.json"
        params = {"limit": 0}  # Don't fetch comments

        try:
            data = self._fetch_json(url, params)
        except RedditScraperError:
            return None

        if not isinstance(data, list) or len(data) < 1:
            return None

        post_listing = data[0]
        children = post_listing.get("data", {}).get("children", [])

        if not children:
            return None

        post_data = children[0].get("data", {})
        return RedditPost.from_json(post_data) if post_data else None

    def get_post_with_comments(
        self,
        post_id: str,
        comment_sort: str = "top",
        comment_limit: int = 500,
        comment_depth: int = 10,
        max_comments: int = 1000,
    ) -> Tuple[Optional[RedditPost], List[RedditComment]]:
        """
        Get a post with its comments.

        Args:
            post_id: Post ID (without t3_ prefix)
            comment_sort: Comment sort (top, new, controversial, best, old, qa)
            comment_limit: Number of comments per request (max ~500)
            comment_depth: Maximum depth of comment tree
            max_comments: Hard cap on total comments to return

        Returns:
            Tuple of (RedditPost, List[RedditComment])
        """
        # Remove t3_ prefix if present
        if post_id.startswith("t3_"):
            post_id = post_id[3:]

        url = f"{self.base_url}/comments/{post_id}.json"
        params = {
            "sort": comment_sort,
            "limit": min(comment_limit, 500),
            "depth": comment_depth,
        }

        data = self._fetch_json(url, params)

        if not isinstance(data, list) or len(data) < 2:
            raise RedditScraperError(f"Unexpected response format for post {post_id}")

        # Parse post
        post_listing = data[0]
        post_children = post_listing.get("data", {}).get("children", [])

        if not post_children:
            return None, []

        post_data = post_children[0].get("data", {})
        post = RedditPost.from_json(post_data) if post_data else None

        # Parse comments
        comment_listing = data[1]
        comment_children = comment_listing.get("data", {}).get("children", [])

        comments: List[RedditComment] = []
        self._flatten_comments(comment_children, depth=0, out=comments, max_comments=max_comments)

        return post, comments

    def _flatten_comments(
        self,
        children: List[Dict[str, Any]],
        depth: int,
        out: List[RedditComment],
        max_comments: int,
    ) -> None:
        """
        Recursively flatten comment tree into a list.

        Ignores "more" placeholders - some comments may be missing in large threads.
        """
        for child in children:
            if len(out) >= max_comments:
                return

            kind = child.get("kind")
            data = child.get("data", {})

            if kind == "t1":
                # This is a comment
                comment = RedditComment.from_json(data, depth=depth)
                out.append(comment)

                # Process replies
                replies = data.get("replies")
                if isinstance(replies, dict):
                    reply_children = replies.get("data", {}).get("children", [])
                    if reply_children:
                        self._flatten_comments(
                            reply_children,
                            depth=depth + 1,
                            out=out,
                            max_comments=max_comments,
                        )

            elif kind == "more":
                # "More comments" placeholder - skip (some comments will be missing)
                continue

    def search_subreddit(
        self,
        subreddit: str,
        query: str,
        sort: str = "relevance",
        time_filter: str = "all",
        limit: int = 25,
    ) -> List[RedditPost]:
        """
        Search posts in a subreddit.

        Args:
            subreddit: Subreddit name
            query: Search query
            sort: Sort method (relevance, hot, top, new, comments)
            time_filter: Time filter (hour, day, week, month, year, all)
            limit: Maximum results

        Returns:
            List of matching posts
        """
        subreddit = subreddit.strip()
        if subreddit.lower().startswith("r/"):
            subreddit = subreddit[2:]

        url = f"{self.base_url}/r/{subreddit}/search.json"
        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
            "restrict_sr": "on",  # Restrict to subreddit
        }

        data = self._fetch_json(url, params)

        posts = []
        children = data.get("data", {}).get("children", [])

        for child in children:
            if child.get("kind") != "t3":
                continue
            post_data = child.get("data", {})
            if post_data:
                posts.append(RedditPost.from_json(post_data))

        return posts

    def get_posts_newer_than(
        self,
        subreddit: str,
        days: int = 30,
        max_posts: int = 1000,
    ) -> List[RedditPost]:
        """
        Get posts from a subreddit newer than a specified number of days.

        Note: Reddit listings are capped at ~1000 posts. If the subreddit has
        more posts than this in the time window, older posts will be missed.

        Args:
            subreddit: Subreddit name
            days: Number of days to look back
            max_posts: Maximum posts to retrieve

        Returns:
            List of posts within the time window
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_ts = cutoff.timestamp()

        all_posts: List[RedditPost] = []
        after: Optional[str] = None

        while len(all_posts) < max_posts:
            posts = self.get_subreddit_posts(
                subreddit=subreddit,
                sort="new",
                limit=100,
                after=after,
            )

            if not posts:
                break

            for post in posts:
                # Skip stickied posts (they can be old)
                if post.stickied:
                    continue

                if post.created_utc < cutoff_ts:
                    # Reached posts older than cutoff
                    return all_posts

                all_posts.append(post)

                if len(all_posts) >= max_posts:
                    return all_posts

            # Set pagination cursor
            after = posts[-1].name

        return all_posts


# Global scraper instance
_scraper: Optional[RedditScraper] = None


def get_scraper() -> RedditScraper:
    """Get or create the global Reddit scraper instance."""
    global _scraper
    if _scraper is None:
        _scraper = RedditScraper()
    return _scraper
