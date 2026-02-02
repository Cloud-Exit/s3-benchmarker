"""S3-compatible storage backend using requests (works with Storadera)."""

import time
from typing import Iterator
from xml.etree import ElementTree

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from requests_aws4auth import AWS4Auth


class S3StorageError(Exception):
    """Base exception for S3 storage operations."""
    pass


class S3UploadError(S3StorageError):
    """Error during S3 upload."""
    pass


class S3DownloadError(S3StorageError):
    """Error during S3 download."""
    pass


class S3ListError(S3StorageError):
    """Error during S3 list operation."""
    pass


class S3RequestsStorage:
    """Storage backend using requests + AWS4Auth (works with Storadera and other providers)."""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str | None = None,
        verbose: bool = False,
        max_retries: int = 5,
        timeout: int = 300,
    ):
        self.bucket = bucket
        self.endpoint = endpoint.rstrip("/")
        self.verbose = verbose
        self.base_url = f"{self.endpoint}/{bucket}"
        self.max_retries = max_retries
        self.timeout = timeout

        # AWS4Auth with empty region (works for most S3-compatible providers)
        self.auth = AWS4Auth(access_key, secret_key, region or "", "s3")
        self.session = requests.Session()
        self.session.auth = self.auth

        # Configure retries for connection errors and timeouts
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=2,  # Exponential backoff: 2, 4, 8, 16, 32 seconds
            status_forcelist=[500, 502, 503, 504],  # Retry on server errors
            allowed_methods=["HEAD", "GET", "PUT", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Disable automatic redirect following
        self.session.max_redirects = 0

        self._ensure_bucket()
        self.name = f"S3 bucket '{bucket}' at {endpoint}"

    def _ensure_bucket(self) -> None:
        """Check bucket exists."""
        resp = self.session.head(self.base_url, timeout=10, allow_redirects=False)
        if resp.status_code == 404:
            raise ValueError(f"Bucket '{self.bucket}' does not exist. Create it first.")
        elif resp.status_code in (301, 302, 307, 308):
            location = resp.headers.get("Location", "unknown")
            raise ValueError(
                f"S3 endpoint returned redirect ({resp.status_code}) to: {location}\n"
                f"Check your S3_ENDPOINT and S3_BUCKET configuration."
            )
        elif resp.status_code != 200:
            raise ValueError(f"Cannot access bucket: {resp.status_code}")

    def save(self, key: str, content: bytes) -> None:
        """Save content to S3 with retry logic."""
        url = f"{self.base_url}/{key}"

        # Manual retry with exponential backoff for timeout errors
        for attempt in range(self.max_retries):
            try:
                resp = self.session.put(
                    url,
                    data=content,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=self.timeout,
                    allow_redirects=False,
                )

                if resp.status_code in (301, 302, 307, 308):
                    location = resp.headers.get("Location", "unknown")
                    raise S3UploadError(f"S3 upload redirected to: {location}")
                if resp.status_code not in (200, 201):
                    raise S3UploadError(f"S3 upload failed: {resp.status_code} {resp.text}")

                # Success
                return

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # Exponential backoff: 1, 2, 4, 8, 16 seconds
                    if self.verbose:
                        print(
                            f"\n  [RETRY] Upload timeout for {key}, "
                            f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})..."
                        )
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    raise S3UploadError(
                        f"Upload failed after {self.max_retries} attempts: {str(e)}"
                    )
            except Exception as e:
                # Non-retryable error
                raise S3UploadError(f"Upload failed: {str(e)}")

    def load(self, key: str) -> bytes | None:
        """Load content from S3 with retry logic."""
        url = f"{self.base_url}/{key}"

        # Manual retry with exponential backoff for timeout errors
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(
                    url, timeout=self.timeout, allow_redirects=False, stream=True
                )

                if resp.status_code == 404:
                    return None
                elif resp.status_code in (301, 302, 307, 308):
                    location = resp.headers.get("Location", "unknown")
                    raise S3DownloadError(f"S3 download redirected to: {location}")
                elif resp.status_code != 200:
                    raise S3DownloadError(f"S3 download failed: {resp.status_code}")

                # Download all chunks
                chunks = []
                chunk_size = 64 * 1024  # 64KB chunks

                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if chunk:
                        chunks.append(chunk)

                return b"".join(chunks)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    if self.verbose:
                        print(
                            f"\n  [RETRY] Download timeout for {key}, "
                            f"retrying in {wait_time}s (attempt {attempt + 1}/{self.max_retries})..."
                        )
                    time.sleep(wait_time)
                else:
                    raise S3DownloadError(
                        f"Download failed after {self.max_retries} attempts: {str(e)}"
                    )
            except Exception as e:
                raise S3DownloadError(f"Download failed: {str(e)}")

        return None

    def exists(self, key: str) -> bool:
        """Check if a key exists in S3."""
        url = f"{self.base_url}/{key}"

        try:
            resp = self.session.head(url, timeout=10, allow_redirects=False)
            return resp.status_code == 200
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # If we can't check, assume it doesn't exist
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from S3."""
        url = f"{self.base_url}/{key}"

        try:
            resp = self.session.delete(url, timeout=10, allow_redirects=False)
            return resp.status_code in (200, 204, 404)  # 404 means already deleted
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            return False

    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys with the given prefix. Returns count of deleted keys."""
        deleted = 0
        try:
            for key in self.list_keys(prefix):
                if self.delete(key):
                    deleted += 1
        except Exception:
            pass
        return deleted

    def list_keys(self, prefix: str = "") -> Iterator[str]:
        """List all keys with the given prefix."""
        continuation_token = None

        while True:
            params = {"list-type": "2", "prefix": prefix}
            if continuation_token:
                params["continuation-token"] = continuation_token

            try:
                resp = self.session.get(
                    self.base_url, params=params, timeout=30, allow_redirects=False
                )
                if resp.status_code in (301, 302, 307, 308):
                    location = resp.headers.get("Location", "unknown")
                    raise S3ListError(f"S3 list redirected to: {location}")
                if resp.status_code != 200:
                    raise S3ListError(f"S3 list failed: {resp.status_code}")

                # Parse XML response
                root = ElementTree.fromstring(resp.content)
                ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

                for content in root.findall(".//s3:Contents", ns):
                    key_elem = content.find("s3:Key", ns)
                    if key_elem is not None and key_elem.text:
                        yield key_elem.text

                # Check for more pages
                is_truncated = root.find(".//s3:IsTruncated", ns)
                if is_truncated is not None and is_truncated.text == "true":
                    token_elem = root.find(".//s3:NextContinuationToken", ns)
                    if token_elem is not None:
                        continuation_token = token_elem.text
                    else:
                        break
                else:
                    break

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                raise S3ListError(f"List operation failed: {str(e)}")
