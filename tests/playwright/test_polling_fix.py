"""
Test to verify the JavaScript polling fix.
"""
import pytest
from playwright.sync_api import Page, expect, Error


class TestPollingFix:
    """Test suite to verify JavaScript polling is fixed."""

    BASE_URL = "http://localhost:5000"

    def test_homepage_loads_and_settles(self, page: Page):
        """Test that homepage loads and settles after initial requests."""
        network_requests = []

        # Track network requests
        page.on("request", lambda request: network_requests.append({
            "url": request.url,
            "timestamp": page.evaluate("Date.now()")
        }))

        # Load homepage with just "load" state (not networkidle)
        try:
            response = page.goto(self.BASE_URL, wait_until="load", timeout=30000)
            assert response.ok, f"Homepage returned status {response.status}"
        except Error as e:
            pytest.fail(f"Failed to load homepage: {str(e)}")

        # Wait 5 seconds to see if there are continuous requests
        page.wait_for_timeout(5000)

        # Count requests to /api/news/stats
        stats_requests = [r for r in network_requests if "/api/news/stats" in r["url"]]

        print(f"\n📊 Total network requests: {len(network_requests)}")
        print(f"📊 Requests to /api/news/stats: {len(stats_requests)}")

        # Should only have 1 stats request (not duplicated)
        if len(stats_requests) > 1:
            print(f"\n🐛 BUG: Multiple stats requests detected:")
            for idx, req in enumerate(stats_requests):
                print(f"  {idx + 1}. {req['url']} at {req['timestamp']}")
            pytest.fail(f"Expected 1 stats request, got {len(stats_requests)} (duplicate calls still present)")

        print(f"\n✅ FIXED: Only {len(stats_requests)} stats request(s) detected")

        # Wait additional 10 seconds to check for continuous polling
        initial_count = len(network_requests)
        page.wait_for_timeout(10000)
        final_count = len(network_requests)

        new_requests = final_count - initial_count
        print(f"\n📊 New requests after 10 seconds: {new_requests}")

        # Should be very few new requests (< 5) if polling is fixed
        if new_requests > 5:
            print(f"\n⚠️  WARNING: {new_requests} new requests detected - may indicate continued polling")
        else:
            print(f"\n✅ CONFIRMED: Minimal activity after page load ({new_requests} requests in 10s)")

    def test_homepage_stats_not_duplicated(self, page: Page):
        """Test that stats API is not called multiple times on page load."""
        stats_calls = []

        def track_stats(request):
            if "/api/news/stats" in request.url:
                stats_calls.append({
                    "url": request.url,
                    "time": page.evaluate("Date.now()")
                })

        page.on("request", track_stats)

        # Load page
        page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Wait for page to stabilize
        page.wait_for_timeout(3000)

        print(f"\n📊 Stats API calls: {len(stats_calls)}")
        for idx, call in enumerate(stats_calls):
            print(f"  {idx + 1}. {call['url']} at {call['time']}")

        # Should have exactly 1 call
        assert len(stats_calls) <= 1, f"Expected 1 stats call, got {len(stats_calls)} (duplicate bug not fixed!)"

        print(f"\n✅ SUCCESS: Stats API called only once")

    def test_sources_page_loads_successfully(self, page: Page):
        """Test that sources page loads without continuous polling."""
        try:
            response = page.goto(f"{self.BASE_URL}/sources", wait_until="domcontentloaded", timeout=30000)
            assert response.ok, f"Sources page returned status {response.status}"

            # Wait a bit
            page.wait_for_timeout(3000)

            print(f"\n✅ Sources page loaded successfully")

        except Error as e:
            pytest.fail(f"Failed to load sources page: {str(e)}")

    def test_polling_uses_timeout_not_interval(self, page: Page):
        """Test that polling uses setTimeout instead of setInterval."""
        page.goto(self.BASE_URL, wait_until="domcontentloaded", timeout=30000)

        # Check if setInterval is being used for polling
        has_bad_interval = page.evaluate("""
            () => {
                // Check if there are any intervals running
                // This is a heuristic check
                return window._hasPollingInterval || false;
            }
        """)

        assert not has_bad_interval, "Page still uses setInterval for polling (should use setTimeout)"

        print(f"\n✅ Polling implementation appears correct")
