"""
Reddit subreddit thread fetcher using no-OAuth scraper.
No API keys required - uses Reddit's public JSON endpoints.
"""
import re
from typing import Dict, List, Optional, Any, Tuple

from reddit.scraper import get_scraper, RedditPost, RedditComment, RedditScraperError
from utils import settings
from utils.ai_methods import sort_by_similarity
from utils.console import print_step, print_substep
from utils.posttextparser import posttextparser
from utils.videos import check_done
from utils.voice import sanitize_text


class SubmissionWrapper:
    """Wrapper to make RedditPost compatible with existing utility functions."""

    def __init__(self, post: RedditPost):
        self.id = post.id
        self.title = post.title
        self.selftext = post.selftext
        self.author = post.author
        self.score = post.score
        self.upvote_ratio = post.upvote_ratio
        self.num_comments = post.num_comments
        self.permalink = post.permalink
        self.url = post.url
        self.over_18 = post.over_18
        self.stickied = post.stickied
        self.subreddit_name = post.subreddit
        self._post = post

    def to_post(self) -> RedditPost:
        return self._post


def get_subreddit_threads(POST_ID: Optional[str] = None) -> Dict[str, Any]:
    """
    Fetches a Reddit thread and its comments using the no-OAuth scraper.
    No API keys required.

    Args:
        POST_ID: Optional specific post ID to fetch

    Returns:
        Dictionary containing thread data and comments
    """
    print_substep("Connecting to Reddit (no-auth mode)...")

    scraper = get_scraper()
    content: Dict[str, Any] = {}
    similarity_score = 0

    # Get subreddit from config or user input
    print_step("Getting subreddit threads...")

    subreddit_name = settings.config["reddit"]["thread"].get("subreddit", "")

    if not subreddit_name:
        subreddit_name = input("What subreddit would you like to pull from? ")
        subreddit_name = re.sub(r"^r/", "", subreddit_name.strip())
        if not subreddit_name:
            subreddit_name = "AskReddit"
            print_substep("Subreddit not defined. Using AskReddit.")
    else:
        # Clean the subreddit name
        if str(subreddit_name).lower().startswith("r/"):
            subreddit_name = subreddit_name[2:]
        print_substep(f"Using subreddit: r/{subreddit_name} from config")

    # Get the submission
    submission: Optional[RedditPost] = None

    try:
        if POST_ID:
            # Specific post ID provided (for queued posts)
            submission = scraper.get_post_by_id(POST_ID)
            if not submission:
                raise RedditScraperError(f"Could not find post with ID: {POST_ID}")

        elif settings.config["reddit"]["thread"].get("post_id"):
            # Post ID from config (single post)
            post_id = str(settings.config["reddit"]["thread"]["post_id"])
            if "+" not in post_id:  # Single post, not multiple
                submission = scraper.get_post_by_id(post_id)
                if not submission:
                    raise RedditScraperError(f"Could not find post with ID: {post_id}")

        elif settings.config["ai"].get("ai_similarity_enabled"):
            # AI sorting based on keyword similarity
            print_substep("Fetching posts for AI similarity sorting...")
            posts = scraper.get_subreddit_posts(subreddit_name, sort="hot", limit=50)

            if not posts:
                raise RedditScraperError(f"No posts found in r/{subreddit_name}")

            keywords = settings.config["ai"].get("ai_similarity_keywords", "").split(",")
            keywords = [keyword.strip() for keyword in keywords if keyword.strip()]

            if keywords:
                keywords_print = ", ".join(keywords)
                print_substep(f"Sorting threads by similarity to: {keywords_print}")

                # Convert posts to format expected by sort_by_similarity
                wrappers = [SubmissionWrapper(post) for post in posts]
                sorted_wrappers, similarity_scores = sort_by_similarity(wrappers, keywords)

                submission, similarity_score = _get_undone_post(
                    sorted_wrappers, subreddit_name, similarity_scores=similarity_scores
                )
            else:
                wrappers = [SubmissionWrapper(post) for post in posts]
                submission = _get_undone_post(wrappers, subreddit_name)

        else:
            # Default: get hot posts
            posts = scraper.get_subreddit_posts(subreddit_name, sort="hot", limit=25)

            if not posts:
                raise RedditScraperError(f"No posts found in r/{subreddit_name}")

            wrappers = [SubmissionWrapper(post) for post in posts]
            submission = _get_undone_post(wrappers, subreddit_name)

    except RedditScraperError as e:
        print_substep(f"Error fetching Reddit data: {e}", style="bold red")
        raise

    if submission is None:
        print_substep("No suitable submission found. Retrying...", style="yellow")
        return get_subreddit_threads(POST_ID)

    # Check if story mode with no comments is okay
    if not submission.num_comments and not settings.config["settings"].get("storymode"):
        print_substep("No comments found. Skipping.", style="bold red")
        exit()

    # Double-check if this post was already done
    wrapper = SubmissionWrapper(submission)
    checked = check_done(wrapper)
    if checked is None:
        print_substep("Post already processed. Finding another...", style="yellow")
        return get_subreddit_threads(POST_ID)

    # Display post info
    upvotes = submission.score
    ratio = submission.upvote_ratio * 100
    num_comments = submission.num_comments
    thread_url = f"https://new.reddit.com{submission.permalink}"

    print_substep(f"Video will be: {submission.title}", style="bold green")
    print_substep(f"Thread url is: {thread_url}", style="bold green")
    print_substep(f"Thread has {upvotes} upvotes", style="bold blue")
    print_substep(f"Thread has a upvote ratio of {ratio:.0f}%", style="bold blue")
    print_substep(f"Thread has {num_comments} comments", style="bold blue")

    if similarity_score:
        print_substep(
            f"Thread has a similarity score up to {round(similarity_score * 100)}%",
            style="bold blue",
        )

    # Build content dictionary
    content["thread_url"] = thread_url
    content["thread_title"] = submission.title
    content["thread_id"] = submission.id
    content["is_nsfw"] = submission.over_18
    content["subreddit"] = subreddit_name
    content["comments"] = []

    if settings.config["settings"].get("storymode"):
        # Story mode - use the post's selftext
        if settings.config["settings"].get("storymodemethod") == 1:
            content["thread_post"] = posttextparser(submission.selftext)
        else:
            content["thread_post"] = submission.selftext
    else:
        # Comment mode - fetch and process comments
        print_substep("Fetching comments...", style="bold blue")

        try:
            _, comments = scraper.get_post_with_comments(
                submission.id,
                comment_sort="top",
                comment_limit=500,
                max_comments=1000,
            )

            # Filter and process comments
            max_len = int(settings.config["reddit"]["thread"].get("max_comment_length", 500))
            min_len = int(settings.config["reddit"]["thread"].get("min_comment_length", 1))

            for comment in comments:
                # Skip non-top-level comments (depth > 0)
                if comment.depth > 0:
                    continue

                # Skip deleted/removed
                if comment.body in ["[removed]", "[deleted]"]:
                    continue

                # Skip stickied comments
                if comment.stickied:
                    continue

                # Sanitize and validate
                sanitized = sanitize_text(comment.body)
                if not sanitized or sanitized.strip() == "":
                    continue

                # Check length constraints
                if len(comment.body) > max_len:
                    continue
                if len(comment.body) < min_len:
                    continue

                # Skip if author is deleted
                if comment.author in ["[deleted]", "[removed]"]:
                    continue

                content["comments"].append({
                    "comment_body": comment.body,
                    "comment_url": comment.permalink,
                    "comment_id": comment.id,
                })

            print_substep(f"Collected {len(content['comments'])} valid comments", style="bold green")

        except RedditScraperError as e:
            print_substep(f"Error fetching comments: {e}", style="yellow")
            # Continue without comments if fetch fails

    print_substep("Received subreddit threads successfully.", style="bold green")
    return content


def _get_undone_post(
    wrappers: List[SubmissionWrapper],
    subreddit_name: str,
    similarity_scores: Optional[List[float]] = None,
) -> Optional[RedditPost] | Tuple[Optional[RedditPost], float]:
    """
    Find a submission that hasn't been processed yet.

    Args:
        wrappers: List of SubmissionWrapper objects
        subreddit_name: Name of the subreddit
        similarity_scores: Optional similarity scores for each submission

    Returns:
        First undone RedditPost, or tuple of (RedditPost, similarity_score) if scores provided
    """
    allow_nsfw = settings.config["settings"].get("allow_nsfw", False)
    min_comments = int(settings.config["reddit"]["thread"].get("min_comments", 20))

    for i, wrapper in enumerate(wrappers):
        # Skip NSFW if not allowed
        if wrapper.over_18 and not allow_nsfw:
            continue

        # Skip stickied posts
        if wrapper.stickied:
            continue

        # Check minimum comments (unless story mode)
        if not settings.config["settings"].get("storymode"):
            if wrapper.num_comments < min_comments:
                continue

        # Check if already done
        if check_done(wrapper) is None:
            continue

        post = wrapper.to_post()

        if similarity_scores is not None and i < len(similarity_scores):
            return post, similarity_scores[i]

        return post

    return None
